"""
这个文档的思路是这个作为 parameter server

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

use_hivemind_log_handler("in_root_logger")
logger = get_logger(__name__)

LRSchedulerBase = getattr(torch.optim.lr_scheduler, "_LRScheduler", None)


def setup_transformers_logging(process_rank: int):
    if is_main_process(process_rank):
        transformers.utils.logging.set_verbosity_info()
        transformers.utils.logging.disable_default_handler()
        transformers.utils.logging.enable_propagation()


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

    #################################################################
    # define the model

    model = BertForMaskedLM.from_pretrained('bert-base-uncased')
    device = training_args.device
    model.to(device)

    # todo: 因为和 run_id 相关, 所以不知道怎么协调不同的 run_id
    # 目前设计的 run_id 包括 ps_server 和 worker
    # validators, local_public_key = utils.make_validators(collaboration_args.run_id)

    dht = DHT(
        start=True,
        initial_peers=collaboration_args.initial_peers,
        client_mode=collaboration_args.client_mode, # client_mode: https://gist.github.com/shizukanaskytree/6a50ec8126dcf946329ef4ea23b55dfb
        # record_validators=validators,
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
        opt,
        num_warmup_steps=training_args.warmup_steps,
        num_training_steps=training_args.total_steps
    )

    optimizer = Optimizer( # 后面要改一个类, 目前借用一下
        dht=dht,
        run_id="ps_server",
        target_batch_size=adjusted_target_batch_size, # not sure
        batch_size_per_step=total_batch_size_per_step, #
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





if __name__ == "__main__":
    main()
