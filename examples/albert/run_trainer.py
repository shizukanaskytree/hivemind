#!/usr/bin/env python3

"""
Logic entry: main function.
"""

import os
import pickle
import sys
from dataclasses import asdict
from pathlib import Path
from tqdm import tqdm  # for our progress bar

import torch
import transformers
from datasets import load_from_disk
from torch.utils.data import DataLoader
from torch_optimizer import Lamb
from transformers import DataCollatorForLanguageModeling, HfArgumentParser, TrainingArguments, set_seed
from transformers.models.albert import AlbertConfig, AlbertForPreTraining, AlbertTokenizerFast
from transformers.optimization import get_linear_schedule_with_warmup
from transformers.trainer import Trainer
from transformers.trainer_utils import is_main_process

from hivemind import DHT, Float16Compression, Optimizer, get_dht_time
from hivemind.utils.logging import get_logger, use_hivemind_log_handler

import utils
from arguments import (
    AlbertTrainingArguments,
    AveragerArguments,
    CollaborationArguments,
    DatasetArguments,
    ProgressTrackerArguments,
)

from transformers import BertTokenizer, BertForMaskedLM

# import debugpy
# debugpy.listen(5678)
# debugpy.wait_for_client()
# debugpy.breakpoint()

use_hivemind_log_handler("in_root_logger")
logger = get_logger(__name__)

LRSchedulerBase = getattr(torch.optim.lr_scheduler, "_LRScheduler", None)


def setup_transformers_logging(process_rank: int):
    if is_main_process(process_rank):
        transformers.utils.logging.set_verbosity_info()
        transformers.utils.logging.disable_default_handler()
        transformers.utils.logging.enable_propagation()


# def get_model(training_args, config, tokenizer):
#     # Find latest checkpoint in output_dir
#     output_dir = Path(training_args.output_dir)
#     logger.info(f'Checkpoint dir {output_dir}, contents {list(output_dir.glob("checkpoint*"))}')
#     latest_checkpoint_dir = max(output_dir.glob("checkpoint*"), default=None, key=os.path.getctime)

#     if latest_checkpoint_dir is not None:
#         logger.info(f"Loading model from {latest_checkpoint_dir}")
#         model = AlbertForPreTraining.from_pretrained(latest_checkpoint_dir)
#     else:
#         logger.info(f"Training from scratch")
#         model = AlbertForPreTraining(config)
#         model.resize_token_embeddings(len(tokenizer))

#     return model


# 一旦用了 for loop 的训练方式, 这个就需要手动调用
class CollaborativeCallback(transformers.TrainerCallback):
    """
    This callback monitors and reports collaborative training progress.
    In case of a catastrophic failure, it can also revert training to a backup.
    """

    def __init__(
        self,
        dht: DHT,
        optimizer: Optimizer,
        model: torch.nn.Module,
        local_public_key: bytes,
        statistics_expiration: float,
        backup_every_steps: int,
    ):
        super().__init__()
        self.model = model
        self.dht, self.optimizer = dht, optimizer
        self.local_public_key = local_public_key
        self.statistics_expiration = statistics_expiration
        self.last_reported_collaboration_step = -1
        self.samples = 0
        self.steps = 0
        self.loss = 0
        self.total_samples_processed = 0
        self.backup_every_steps = backup_every_steps
        self.latest_backup = self.backup_state()

    # on train begin
    def on_train_begin(
        self, args: TrainingArguments, state: transformers.TrainerState, control: transformers.TrainerControl, **kwargs
    ):
        logger.info("Loading state from peers")
        self.optimizer.load_state_from_peers()

    # on step end
    def on_step_end(
        self, args: TrainingArguments, state: transformers.TrainerState, control: transformers.TrainerControl, **kwargs
    ):
        control.should_log = True
        if not self.params_are_finite():
            self.restore_from_backup(self.latest_backup)
            return control

        local_progress = self.optimizer.local_progress

        if state.log_history:
            self.loss += state.log_history[-1]["loss"]
            self.steps += 1

            if self.optimizer.local_epoch != self.last_reported_collaboration_step:
                self.last_reported_collaboration_step = self.optimizer.local_epoch
                self.total_samples_processed += self.samples
                samples_per_second = local_progress.samples_per_second
                statistics = utils.LocalMetrics(
                    step=self.optimizer.local_epoch,
                    samples_per_second=samples_per_second,
                    samples_accumulated=self.samples,
                    loss=self.loss,
                    mini_steps=self.steps,
                )
                logger.info(f"Step #{self.optimizer.local_epoch}")
                logger.info(f"Your current contribution: {self.total_samples_processed} samples")
                logger.info(f"Performance: {samples_per_second:.3f} samples/sec")
                if self.steps:
                    logger.info(f"Local loss: {self.loss / self.steps:.5f}")
                if self.optimizer.local_epoch % self.backup_every_steps == 0:
                    self.latest_backup = self.backup_state()

                self.loss = 0
                self.steps = 0
                if self.optimizer.is_synchronized_with_peers():
                    self.dht.store(
                        key=self.optimizer.run_id + "_metrics",
                        subkey=self.local_public_key,
                        value=statistics.dict(),
                        expiration_time=get_dht_time() + self.statistics_expiration,
                        return_future=True,
                    )

        self.samples = local_progress.samples_accumulated

        return control

    @torch.no_grad()
    def params_are_finite(self):
        # used in on_step_end
        for param in self.model.parameters():
            if not torch.all(torch.isfinite(param)):
                return False
        return True

    @torch.no_grad()
    def backup_state(self) -> bytes:
        # used in on_step_end
        # store model state and optimizer state.
        return pickle.dumps({"model": self.model.state_dict(), "optimizer": self.optimizer.state_dict()})

    @torch.no_grad()
    def restore_from_backup(self, backup: bytes):
        # used in on_step_end
        state = pickle.loads(backup)
        self.model.load_state_dict(state["model"])
        self.optimizer.load_state_dict(state["optimizer"])


class NoOpScheduler(LRSchedulerBase):
    """Dummy scheduler for transformers.Trainer. The real scheduler is defined in Optimizer.scheduler"""

    def get_lr(self):
        return [group["lr"] for group in self.optimizer.param_groups]

    def print_lr(self, *args, **kwargs):
        if self.optimizer.scheduler:
            return self.optimizer.scheduler.print_lr(*args, **kwargs)

    def step(self):
        self._last_lr = self.get_lr()

    def state_dict(self):
        return {}

    def load_state_dict(self, *args, **kwargs):
        logger.debug("Called NoOpScheduler.load_state_dict")


class MeditationsDataset(torch.utils.data.Dataset):
    def __init__(self, encodings):
        self.encodings = encodings

    def __getitem__(self, idx):
        return {key: torch.tensor(val[idx]) for key, val in self.encodings.items()}

    def __len__(self):
        return len(self.encodings.input_ids)


def main():
    # get the args from cmds or default values
    parser = HfArgumentParser(
        (
            AlbertTrainingArguments,
            DatasetArguments,
            CollaborationArguments,
            AveragerArguments,
            ProgressTrackerArguments,
        )
    )
    training_args, dataset_args, collaboration_args, averager_args, tracker_args = parser.parse_args_into_dataclasses()

    logger.info(f"Found {len(collaboration_args.initial_peers)} initial peers: {collaboration_args.initial_peers}")

    setup_transformers_logging(training_args.local_rank)
    logger.info(f"Training/evaluation parameters:\n{training_args}")

    # Set seed before initializing model.
    set_seed(training_args.seed)

    model = BertForMaskedLM.from_pretrained('bert-base-uncased')

    # config = AlbertConfig.from_pretrained(dataset_args.config_path, cache_dir=dataset_args.cache_dir)
    # try:
    #     tokenizer = AlbertTokenizerFast.from_pretrained(dataset_args.tokenizer_path, cache_dir=dataset_args.cache_dir)
    # except OSError:
    #     logger.fatal(
    #         f"No tokenizer data found in {dataset_args.tokenizer_path}, "
    #         f"please run ./tokenize_wikitext103.py before running this"
    #     )
    #     sys.exit(1)

    # model = get_model(training_args, config, tokenizer)
    device = training_args.device
    model.to(device)

    with open('meditations/clean.txt', 'r') as fp:
        text = fp.read().split('\n')

    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    inputs = tokenizer(text, return_tensors='pt', max_length=512, truncation=True, padding='max_length')
    inputs['labels'] = inputs.input_ids.detach().clone()

    # create random array of floats with equal dimensions to input_ids tensor
    rand = torch.rand(inputs.input_ids.shape)
    # create mask array
    mask_arr = (rand < 0.15) * (inputs.input_ids != 101) * \
            (inputs.input_ids != 102) * (inputs.input_ids != 0)

    selection = []

    for i in range(inputs.input_ids.shape[0]):
        selection.append(
            torch.flatten(mask_arr[i].nonzero()).tolist()
        )

    for i in range(inputs.input_ids.shape[0]):
        inputs.input_ids[i, selection[i]] = 103

    dataset = MeditationsDataset(inputs)

    loader = torch.utils.data.DataLoader(dataset, batch_size=16, shuffle=True)

    # tokenized_datasets = load_from_disk(Path(dataset_args.dataset_path))
    # tokenized_datasets 和使用: https://gist.github.com/shizukanaskytree/0c33a25036fa434905dda15dd2858e87

    # This data collator will take care of randomly masking the tokens.
    # data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer)
    # data_collator: https://gist.github.com/shizukanaskytree/501bc1c59865609084bd020ed98727e9

    validators, local_public_key = utils.make_validators(collaboration_args.run_id)

    dht = DHT(
        start=True,
        initial_peers=collaboration_args.initial_peers,
        client_mode=collaboration_args.client_mode, # client_mode: https://gist.github.com/shizukanaskytree/6a50ec8126dcf946329ef4ea23b55dfb
        record_validators=validators,
        use_ipfs=collaboration_args.use_ipfs,
        host_maddrs=collaboration_args.host_maddrs,
        announce_maddrs=collaboration_args.announce_maddrs,
        identity_path=collaboration_args.identity_path,
    )
    utils.log_visible_maddrs(dht.get_visible_maddrs(), only_p2p=collaboration_args.use_ipfs)

    total_batch_size_per_step = training_args.per_device_train_batch_size * training_args.gradient_accumulation_steps
    # if torch.cuda.device_count() != 0:
    #     total_batch_size_per_step *= torch.cuda.device_count()

    adjusted_target_batch_size = collaboration_args.target_batch_size - collaboration_args.batch_size_lead

    # We need to make such a lambda function instead of just an optimizer instance
    # to make hivemind.Optimizer(..., offload_optimizer=True) work

    # wxf: hivemind.Optimizer(..., offload_optimizer=True) <= match my purpose.

    # wxf: what's the diff lamb and adamw?
    opt = lambda params: Lamb(
        params,
        lr=training_args.learning_rate,
        betas=(training_args.adam_beta1, training_args.adam_beta2),
        eps=training_args.adam_epsilon,
        weight_decay=training_args.weight_decay,
        clamp_value=training_args.clamp_value,
        debias=True,
    )

    no_decay = ["bias", "LayerNorm.weight"]
    params = [
        {
            "params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
            "weight_decay": training_args.weight_decay,
        },
        {
            "params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)],
            "weight_decay": 0.0,
        },
    ]

    scheduler = lambda opt: get_linear_schedule_with_warmup(
        opt, num_warmup_steps=training_args.warmup_steps, num_training_steps=training_args.total_steps
    )

    optimizer = Optimizer(
        dht=dht,
        run_id=collaboration_args.run_id,
        target_batch_size=adjusted_target_batch_size,
        batch_size_per_step=total_batch_size_per_step,
        optimizer=opt,
        params=params,
        scheduler=scheduler,
        matchmaking_time=collaboration_args.matchmaking_time,
        averaging_timeout=collaboration_args.averaging_timeout,
        offload_optimizer=True,
        delay_optimizer_step=True,
        delay_grad_averaging=True,
        client_mode=collaboration_args.client_mode,
        grad_compression=Float16Compression(),
        state_averaging_compression=Float16Compression(),
        averager_opts={"bandwidth": collaboration_args.bandwidth, **asdict(averager_args)},
        tracker_opts=asdict(tracker_args),
        verbose=True,
    )

    # wxf:
    # 如果我不用这个 collaborative 是不是就是单点贡献了呢?
    # 我记得有一个模式是这样的, 不合作模式!
    collaborative = CollaborativeCallback(
        dht,
        optimizer,
        model,
        local_public_key,
        collaboration_args.statistics_expiration,
        collaboration_args.backup_every_steps,
    )


    epochs = 200

    # wxf:
    # optimizer 是不是就是这么调用的呢?
    # - optimizer.zero_grad()
    # - optimizer.step()
    # 是的, 作者在代码注释部分写了.

    #wxf# 可是我不想用 Trainer, 模仿这个写
    #wxf# >>> model = transformers.AutoModel("albert-xxlarge-v2")
    #wxf# >>> dht = hivemind.DHT(initial_peers=INITIAL_PEERS, start=True)
    #wxf# >>> opt = hivemind.Optimizer(dht=dht, run_id="run_42", batch_size_per_step=4, target_batch_size=4096,
    #wxf# >>>                          params=model.parameters(), optimizer=lambda params: torch.optim.Adam(params))
    #wxf# >>> while True:
    #wxf# >>>     loss = compute_loss_on_batch(model, batch_size=4)
    #wxf# >>>     opt.zero_grad()
    #wxf# >>>     loss.backward()
    #wxf# >>>     opt.step()  # <-- train collaboratively with any peers that use the same prefix (run_42)


    for epoch in range(epochs):
        # setup loop with TQDM and dataloader
        loop = tqdm(loader, leave=True)
        for batch in loop:
            # initialize calculated gradients (from prev step)
            optimizer.zero_grad()

            # pull all tensor batches required for training
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            # process
            outputs = model(input_ids, attention_mask=attention_mask,
                            labels=labels)
            # extract loss
            loss = outputs.loss
            # calculate loss for every parameter that needs grad update
            loss.backward()

            # update parameters
            optimizer.step()

            # print relevant info to progress bar
            loop.set_description(f'Epoch {epoch}')
            loop.set_postfix(loss=loss.item())


    # class TrainerWithIndependentShuffling(Trainer):

    #     def get_train_dataloader(self) -> DataLoader:
    #         """Shuffle data independently for each peer to avoid duplicating batches [important for quality]"""
    #         torch.manual_seed(hash(local_public_key))
    #         return super().get_train_dataloader()

    # trainer = TrainerWithIndependentShuffling(
    #     model=model,
    #     args=training_args,
    #     tokenizer=tokenizer,
    #     data_collator=data_collator,
    #     train_dataset=tokenized_datasets["train"] if training_args.do_train else None,
    #     eval_dataset=tokenized_datasets["validation"] if training_args.do_eval else None,
    #     optimizers=(optimizer, NoOpScheduler(optimizer)),
    #     callbacks=[
    #         CollaborativeCallback(
    #             dht,
    #             optimizer,
    #             model,
    #             local_public_key,
    #             collaboration_args.statistics_expiration,
    #             collaboration_args.backup_every_steps,
    #         )
    #     ],
    # )
    # trainer.remove_callback(transformers.trainer_callback.PrinterCallback)
    # trainer.remove_callback(transformers.trainer_callback.ProgressCallback)

    # # Training
    # if training_args.do_train:
    #     latest_checkpoint_dir = max(
    #         Path(training_args.output_dir).glob("checkpoint*"), default=None, key=os.path.getctime
    #     )

    #     trainer.train(model_path=latest_checkpoint_dir)


if __name__ == "__main__":
    main()
