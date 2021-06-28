# import debugpy
# debugpy.listen(5678)
# debugpy.wait_for_client()
# debugpy.breakpoint()

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from itertools import chain, zip_longest
from os.path import exists, join
from typing import Optional

import hivemind
import jieba
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import transformers
import wandb
from hivemind.utils.logging import get_logger
from sklearn.model_selection import train_test_split
from torch.nn import CrossEntropyLoss, DataParallel

# adv
from torch.nn.utils import clip_grad_norm_
from torch.optim import Adam
from torch.utils.data import DataLoader, Dataset
from torch.utils.tensorboard import SummaryWriter
from torch_optimizer import Lamb
from torchtext.data.metrics import bleu_score
from tqdm import tqdm
from transformers import (
    BertTokenizer,
    GPT2Config,
    GPT2LMHeadModel,
    GPT2Tokenizer,
    HfArgumentParser,
    get_cosine_schedule_with_warmup,
)
from whatsmyip.ip import get_ip
from whatsmyip.providers import GoogleDnsProvider

import metrics_utils
from arguments import (
    AveragerArguments,
    BaseTrainingArguments,
    CollaborativeOptimizerArguments,
)
from utils import Adam_GC

tqdm.pandas()
PAD = "[PAD]"
pad_id = 0

torch.multiprocessing.set_sharing_strategy('file_system')
logger = get_logger(__name__)


@dataclass
class CoordinatorArguments(BaseTrainingArguments):
    """
    Note: You might want to have several initial peers so that if one dies,
    new workers still can join the collaboration via alive initial peers' addresses.
    Specify initial_peers argument for that purpose
    """

    address: Optional[str] = field(
        default=None,
        metadata={
            "help": "This machine's network address. Use public IP for global experiments, "
            "local address for private runs"
        },
    )
    refresh_period: float = field(
        default=30,
        metadata={
            "help": "Coordinator will fetch keys from DHT once in this many seconds"
        },
    )
    wandb_project: Optional[str] = field(
        default=None, metadata={"help": "Learning curves will be published there"}
    )
    save_checkpoint_step_interval: int = field(
        default=5,
        metadata={
            "help": "Coordinator will load and save state from peers once every that many steps"
        },
    )
    model_config_path: str = field(
        default="https://s3.amazonaws.com/models.huggingface.co/bert/albert-large-v2-config.json",
        metadata={"help": "Path to the model config"},
    )
    repo_path: Optional[str] = field(
        default=None,
        metadata={
            "help": "Path to HuggingFace repo in which coordinator will upload the model and optimizer states"
        },
    )
    upload_interval: Optional[float] = field(
        default=None,
        metadata={
            "help": "Coordinator will upload model once in this many seconds"},
    )


class CheckpointHandler:
    def __init__(
        self,
        coordinator_args: CoordinatorArguments,
        collab_optimizer_args: CollaborativeOptimizerArguments,
        averager_args: AveragerArguments,
        dht: hivemind.DHT,
    ):
        self.save_checkpoint_step_interval = (
            coordinator_args.save_checkpoint_step_interval
        )
        self.repo_path = coordinator_args.repo_path
        self.upload_interval = coordinator_args.upload_interval
        self.previous_step = -1

        config = GPT2Config.from_json_file(
            "./config/model_config_dialogue_small.json"
        )
        self.model = GPT2LMHeadModel(config=config)

        no_decay = ["bias", "LayerNorm.bias", "LayerNorm.weight"]
        param_optimizer = list(self.model.named_parameters())
        # todo
        optimizer_grouped_parameters = [
            {
                "params": [
                    p for n, p in param_optimizer if not any(nd in n for nd in no_decay)
                ],
                "weight_decay": 1e-7,
            },  # hardcode now
            {
                "params": [
                    p for n, p in param_optimizer if any(nd in n for nd in no_decay)
                ],
                "weight_decay": 0.0,
            },
        ]

        # todo
        opt = Adam_GC(optimizer_grouped_parameters, lr=1e-6)  # hardcode

        adjusted_target_batch_size = (
            collab_optimizer_args.target_batch_size
            - collab_optimizer_args.batch_size_lead
        )

        self.collaborative_optimizer = hivemind.CollaborativeOptimizer(
            opt=opt,
            dht=dht,
            prefix=experiment_prefix,
            compression_type=hivemind.utils.CompressionType.Value(
                collab_optimizer_args.compression
            ),
            throughput=collab_optimizer_args.bandwidth,
            target_batch_size=adjusted_target_batch_size,
            client_mode=collab_optimizer_args.client_mode,
            verbose=True,
            start=True,
            **asdict(averager_args),
        )
        self.previous_timestamp = time.time()

    def is_time_to_save_state(self, cur_step):
        if self.save_checkpoint_step_interval is None:
            return False
        elif cur_step - self.previous_step >= self.save_checkpoint_step_interval:
            return True
        else:
            return False

    def save_state(self, cur_step):
        self.collaborative_optimizer.load_state_from_peers()
        self.previous_step = cur_step

    def is_time_to_upload(self):
        if self.repo_path is None:
            return False
        elif time.time() - self.previous_timestamp >= self.upload_interval:
            return True
        else:
            return False

    def upload_checkpoint(self, current_loss):
        self.model.save_pretrained(self.repo_path)
        torch.save(
            self.collaborative_optimizer.opt.state_dict(),
            f"{self.repo_path}/optimizer_state.pt",
        )
        self.previous_timestamp = time.time()
        try:
            subprocess.run("git add --all", shell=True,
                           check=True, cwd=self.repo_path)
            current_step = (
                self.collaborative_optimizer.collaboration_state.optimizer_step
            )
            subprocess.run(
                f"git commit -m 'Step {current_step}, loss {current_loss:.3f}'",
                shell=True,
                check=True,
                cwd=self.repo_path,
            )
            subprocess.run("git push", shell=True,
                           check=True, cwd=self.repo_path)
        except subprocess.CalledProcessError as e:
            logger.warning("Error while uploading model:", e.output)


if __name__ == "__main__":
    parser = HfArgumentParser(
        (CoordinatorArguments, CollaborativeOptimizerArguments, AveragerArguments)
    )
    (
        coordinator_args,
        collab_optimizer_args,
        averager_args,
    ) = parser.parse_args_into_dataclasses()

    if coordinator_args.address is None:
        logger.warning(
            "No address specified. Attempting to infer address from DNS.")
        coordinator_args.address = get_ip(GoogleDnsProvider)

    experiment_prefix = coordinator_args.experiment_prefix
    validators, local_public_key = metrics_utils.make_validators(
        experiment_prefix)
    dht = hivemind.DHT(
        start=True,
        listen_on=coordinator_args.dht_listen_on,
        endpoint=f"{coordinator_args.address}:*",
        initial_peers=coordinator_args.initial_peers,
        record_validators=validators,
    )

    logger.info(f"Running DHT root at {coordinator_args.address}:{dht.port}")

    if coordinator_args.wandb_project is not None:
        wandb.init(project=coordinator_args.wandb_project)

    current_step = 0

    checkpoint_handler = CheckpointHandler(
        coordinator_args, collab_optimizer_args, averager_args, dht
    )

    while True:
        metrics_dict = dht.get(experiment_prefix + "_metrics", latest=True)
        if metrics_dict is not None:
            metrics_dict = metrics_dict.value
            metrics = [
                metrics_utils.LocalMetrics.parse_obj(metrics_dict[peer].value)
                for peer in metrics_dict
            ]
            latest_step = max(item.step for item in metrics)
            if latest_step != current_step:
                current_step = latest_step
                alive_peers = 0
                num_batches = 0
                sum_loss = 0
                num_samples = 0
                sum_perf = 0
                sum_mini_steps = 0
                for item in metrics:
                    sum_loss += item.loss
                    alive_peers += 1
                    sum_perf += item.samples_per_second
                    num_samples += item.samples_accumulated
                    sum_mini_steps += item.mini_steps
                current_loss = sum_loss / sum_mini_steps

                if coordinator_args.wandb_project is not None:
                    wandb.log(
                        {
                            "loss": current_loss,
                            "alive peers": alive_peers,
                            "samples": num_samples,
                            "performance": sum_perf,
                            "step": latest_step,
                        }
                    )
                if checkpoint_handler.is_time_to_save_state(current_step):
                    checkpoint_handler.save_state(current_step)
                    if checkpoint_handler.is_time_to_upload():
                        checkpoint_handler.upload_checkpoint(current_loss)
                logger.info(f"Step #{current_step}\tloss = {current_loss:.5f}")
        logger.debug("Peer is still alive...")
        time.sleep(coordinator_args.refresh_period)
