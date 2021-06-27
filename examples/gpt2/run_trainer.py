import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
debugpy.breakpoint()

import argparse
import json
import logging
import os
import random
import re
import shutil
import sys
from dataclasses import asdict
from datetime import datetime
from itertools import chain, zip_longest
from os.path import exists, join
from pathlib import Path
from typing import Any, Dict

import hivemind
import jieba
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.multiprocessing
import transformers
from datasets import load_from_disk
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
from transformers import (AlbertConfig, AlbertForPreTraining,
                          AlbertTokenizerFast, BertTokenizer,
                          DataCollatorForLanguageModeling, GPT2Config,
                          GPT2LMHeadModel, GPT2Tokenizer, HfArgumentParser,
                          TrainingArguments, get_cosine_schedule_with_warmup,
                          set_seed)
from transformers.optimization import get_linear_schedule_with_warmup
from transformers.trainer import Trainer
from transformers.trainer_utils import is_main_process

import metrics_utils
from arguments import (AlbertTrainingArguments, CollaborationArguments,
                       DatasetArguments, GPT2TrainingArguments)
from utils import Adam_GC

tqdm.pandas()
PAD = '[PAD]'
pad_id = 0

torch.multiprocessing.set_sharing_strategy('file_system')

logger = logging.getLogger(__name__)


class MyDataset(Dataset):
    def __init__(self, data_list):
        self.data_list = data_list

    def __getitem__(self, index):
        input_ids = self.data_list[index]
        return input_ids

    def __len__(self):
        return len(self.data_list)


class CollaborativeCall():
    def __init__(self, dht: hivemind.DHT, optimizer: hivemind.CollaborativeOptimizer,
                 model: torch.nn.Module, local_public_key: bytes, statistics_expiration: float):
        super().__init__()
        self.model = model
        self.dht, self.collaborative_optimizer = dht, optimizer
        self.local_public_key = local_public_key
        self.statistics_expiration = statistics_expiration
        self.last_reported_collaboration_step = -1
        self.previous_state = self.get_current_state()
        self.samples = 0
        self.steps = 0
        self.loss = 0
        self.total_samples_processed = 0

    # Place this function at the beginning of the training of gpt2
    def on_train_begin(self, **kwargs):
        logger.info('Loading state from peers')
        self.collaborative_optimizer.load_state_from_peers()

    # Place this function at the beginning of the training of gpt2
    def on_step_end(self, loss_train, **kwargs):
        if not self.params_are_finite():
            self.load_from_state(self.previous_state)

        self.previous_state = self.get_current_state()

        self.loss += loss_train
        self.steps += 1

        # print('self.ccollaborative_optimizer.local_step', self.collaborative_optimizer.local_step)
        # print('self.last_reported_collaboration_step', self.last_reported_collaboration_step)

        # if self.collaborative_optimizer.local_step != self.last_reported_collaboration_step:
        self.last_reported_collaboration_step = self.collaborative_optimizer.local_step
        self.total_samples_processed += self.samples
        samples_per_second = self.collaborative_optimizer.performance_ema.samples_per_second

        statistics = metrics_utils.LocalMetrics(
            step=self.collaborative_optimizer.local_step,
            samples_per_second=samples_per_second,
            samples_accumulated=self.samples,
            loss=self.loss,
            mini_steps=self.steps)

        logger.info(f"Step {self.collaborative_optimizer.local_step}")
        logger.info(
            f"Your current contribution: {self.total_samples_processed} samples")
        if self.steps:
            logger.info(f"Local loss: {self.loss / self.steps}")

        self.loss = 0
        self.steps = 0
        if self.collaborative_optimizer.is_synchronized:
            print('=== collaborative_optimizer.is_synchronized ===')
            self.dht.store(key=self.collaborative_optimizer.prefix + "_metrics",
                           subkey=self.local_public_key, value=statistics.dict(),
                           expiration_time=hivemind.get_dht_time() + self.statistics_expiration,
                           return_future=True)

        self.samples = self.collaborative_optimizer.local_samples_accumulated

    @torch.no_grad()
    def get_current_state(self) -> Dict[str, Any]:
        return {
            'model': self.model.state_dict(),
            'opt': self.collaborative_optimizer.opt.state_dict()
        }

    @torch.no_grad()
    def load_from_state(self, state):
        self.model.load_state_dict(state['model'])
        self.collaborative_optimizer.opt.load_state_dict(state['opt'])

    # 这个函数和 callback 接口无关
    @torch.no_grad()
    def params_are_finite(self):
        for param in self.model.parameters():
            if not torch.all(torch.isfinite(param)):
                return False
        return True


class dialogpt:

    def __init__(self, args):
        self.args = args
        self.config = GPT2Config.from_json_file(args.config)
        self.model = GPT2LMHeadModel(config=self.config)
        self.tokenizer = BertTokenizer(vocab_file=args.vocab)
        self.valid_response = []
        self.valid_question = []
        if args.make_tokenize:
            self.tb_writer = SummaryWriter()
        else:
            self.tb_writer = None

    def load_model(self, dir):
        self.model = GPT2LMHeadModel.from_pretrained(dir)

    def get_model(self):
        return self.model

    def tokenizer_sen(self, sen):
        # 5 for the rooms for [sep] and [start]...
        max_count = self.args.max_len-5
        # tokenizer one sentence output tensor
        if len(sen) > max_count:
            sen = sen[:max_count]
        final = [self.tokenizer.cls_token_id]
        for word in sen:
            final.append(self.tokenizer.convert_tokens_to_ids(word))
        final.append(self.tokenizer.sep_token_id)
        return final

    def tokenize_raw_data(self):
        raw_data = pd.read_csv(self.args.raw_train_csv)
        raw_data = raw_data[['question', 'response']]
        raw_data['question'] = raw_data['question'].astype(str)
        raw_data['response'] = raw_data['response'].astype(str)
        raw_data.dropna()
        # 此方法默认忽略token_type_ids的问题不同句问题，只进行tokenizer作为唯一input，不给NN提供问答属于不同句的信息，直接强行自回归
        raw_list = raw_data.progress_apply(lambda x: self.tokenizer_sen(
            x['question'])+self.tokenizer_sen(x['response'])[1:], axis=1)
        raw_list.name = 'token_list'
        raw_list.to_csv(self.args.saved_token_train)

        raw_data = pd.read_csv(self.args.raw_valid_csv)
        raw_data = raw_data[['question', 'response']]
        raw_data['question'] = raw_data['question'].astype(str)
        raw_data['response'] = raw_data['response'].astype(str)
        raw_data.dropna()
        # 此方法默认忽略token_type_ids的问题不同句问题，只进行tokenizer作为唯一input，不给NN提供问答属于不同句的信息，直接强行自回归
        raw_list = raw_data.progress_apply(lambda x: self.tokenizer_sen(
            x['question'])+self.tokenizer_sen(x['response'])[1:], axis=1)
        # record the response text from validate dataset
        for text in raw_data['response']:
            text = text.lower()
            text = jieba.cut(text, cut_all=False)
            text = [t for t in text]
            self.valid_response.append([text])
        # record the question text from validate dataset
        for text in raw_data['question']:
            text = text.lower()
            self.valid_question.append(text)
        # note, I have not removed the comma, etc.
        # print(self.valid_response)
        raw_list.name = 'token_list'
        raw_list.to_csv(self.args.saved_token_valid)

    def top_k_top_p_filtering(logits, top_k=0, top_p=0.0, filter_value=-float('Inf')):
        """ Filter a distribution of logits using top-k and/or nucleus (top-p) filtering
            Args:
                logits: logits distribution shape (vocabulary size)
                top_k > 0: keep only top k tokens with highest probability (top-k filtering).
                top_p > 0.0: keep the top tokens with cumulative probability >= top_p (nucleus filtering).
                    Nucleus filtering is described in Holtzman et al. (http://arxiv.org/abs/1904.09751)
            From: https://gist.github.com/thomwolf/1a5a29f6962089e871b94cbd09daf317
        """
        # assert logits.dim() == 1  # batch size 1 for now - could be updated for more but the code would be less clear
        top_k = min(top_k, logits.size(-1))  # Safety check
        if top_k > 0:
            # Remove all tokens with a probability less than the last token of the top-k
            # torch.topk()返回最后一维最大的top_k个元素，返回值为二维(values,indices)
            # ...表示其他维度由计算机自行推断
            indices_to_remove = logits < torch.topk(logits, top_k)[
                0][..., -1, None]
            # 对于topk之外的其他元素的logits值设为负无穷
            logits[indices_to_remove] = filter_value

        if top_p > 0.0:
            sorted_logits, sorted_indices = torch.sort(
                logits, descending=True)  # 对logits进行递减排序
            cumulative_probs = torch.cumsum(
                F.softmax(sorted_logits, dim=-1), dim=-1)

            # Remove tokens with cumulative probability above the threshold
            sorted_indices_to_remove = cumulative_probs > top_p
            # Shift the indices to the right to keep also the first token above the threshold
            sorted_indices_to_remove[...,
                                     1:] = sorted_indices_to_remove[..., :-1].clone()
            sorted_indices_to_remove[..., 0] = 0

            indices_to_remove = sorted_indices[sorted_indices_to_remove]
            logits[indices_to_remove] = filter_value
        return logits

    def get_opt(self):
        param_optimizer = list(self.model.named_parameters())
        no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
        optimizer_grouped_parameters = [
            {'params': [p for n, p in param_optimizer if not any(
                nd in n for nd in no_decay)], 'weight_decay': self.args.weight_decay},
            {'params': [p for n, p in param_optimizer if any(nd in n for nd in no_decay)], 'weight_decay': 0.0}]
        optimizer = Adam_GC(optimizer_grouped_parameters, lr=self.args.lr)
        return optimizer

    def get_collaborative_opt(self):
        return self.collaborative_opt

    def set_collaborative_opt(self, collaborative_opt):
        self.collaborative_opt = collaborative_opt

    def set_collaborative_call(self, collaborative_call):
        self.collaborative_call = collaborative_call

    def get_scheduler(self, optimizer):
        cosine_warmup_schedule = get_cosine_schedule_with_warmup(optimizer,
                                                                 num_warmup_steps=int(
                                                                     self.args.epochs*self.args.warmup_proportion),
                                                                 num_training_steps=self.args.epochs, num_cycles=0.5, last_epoch=-1)

        return cosine_warmup_schedule

    def train(self):
        # DHT peer
        self.collaborative_call.on_train_begin()

        saved_token_train = pd.read_csv(
            self.args.saved_token_train)['token_list']
        saved_token_train = saved_token_train[saved_token_train.apply(
            lambda x:len(x) <= self.args.max_len-5)]
        # add validation data
        saved_token_valid = pd.read_csv(
            self.args.saved_token_valid)['token_list']
        saved_token_valid = saved_token_valid[saved_token_valid.apply(
            lambda x:len(x) <= self.args.max_len-5)]
        # [pad]补
        print('preprocessing for padding...')
        saved_token_train = saved_token_train.progress_apply(
            lambda x: eval(x) + (self.args.max_len-len(eval(x)))*[0])
        saved_token_valid = saved_token_valid.progress_apply(
            lambda x: eval(x) + (self.args.max_len-len(eval(x)))*[0])
        print('tensorize...')
        train_tensor_list = saved_token_train.progress_apply(
            lambda x: torch.tensor(x)).to_list()
        valid_tensor_list = saved_token_valid.progress_apply(
            lambda x: torch.tensor(x)).to_list()
        print('prepare dataloader...')
        dataset = MyDataset(train_tensor_list)
        valid_dataset = MyDataset(valid_tensor_list)
        dataloader = DataLoader(
            dataset, batch_size=self.args.batch_size, shuffle=True)
        valid_dataloader = DataLoader(
            valid_dataset, batch_size=self.args.batch_size, shuffle=False)
        del saved_token_train, train_tensor_list, saved_token_valid, valid_tensor_list

        # GPU
        print('setup gpu')
        # self.model = torch.nn.DataParallel(self.model)
        self.model.cuda()

        # Prepare optimizer
        print('setup optimizer...')
        optimizer = self.get_opt()
        # cos warmup
        cosine_warmup_schedule = self.get_scheduler(optimizer)

        loss_fct = CrossEntropyLoss(ignore_index=pad_id, reduction='sum')

        print('start training')

        parent_dir = self.args.save_path
        if not os.path.exists(parent_dir):
            os.mkdir(parent_dir)

        train_plot_record = []
        valid_plot_record = []

        # collaborative opt
        optimizer = self.get_collaborative_opt()

        for epoch in range(self.args.epochs):
            self.model.train()
            _loss = []
            for batch in tqdm(dataloader):
                optimizer.zero_grad()
                batch = batch.cuda(non_blocking=True)
                output = self.model(batch)
                logits = output[0]
                shift_logits = logits[..., :-1, :].contiguous()
                shift_labels = batch[..., 1:].contiguous().cuda()
                loss = loss_fct(
                    shift_logits.view(-1, shift_logits.size(-1)), shift_labels.view(-1))
                loss.backward()
                _loss.append(loss.item())
                # gradient clip
                clip_grad_norm_(self.model.parameters(),
                                self.args.max_clip_norm)
                optimizer.step()
                # free might_accumulatd tensors for OOM
                del batch, output, logits
                cosine_warmup_schedule.step()
                # Hivemind collaborative
                self.collaborative_call.on_step_end(loss.item())

            # # calculate validate loss
            # with torch.no_grad():
            #     self.model.eval()
            #     valid_loss = []
            #     for batch in tqdm(valid_dataloader):
            #         batch = batch.cuda(non_blocking=True)
            #         output = self.model(batch)
            #         logits = output[0]
            #         shift_logits = logits[..., :-1, :].contiguous()
            #         shift_labels = batch[..., 1:].contiguous().cuda()
            #         loss = loss_fct(
            #             shift_logits.view(-1, shift_logits.size(-1)), shift_labels.view(-1))
            #         valid_loss.append(loss.item())
            #         # free might_accumulatd tensors for OOM
            #         del batch, output, logits

            # # calculate validate BLEU value
            # with torch.no_grad():
            #     self.model.eval()
            #     candidate_corpus = []
            #     for sen in self.valid_question:
            #         encoded_token = [self.tokenizer.encode(sen)]
            #         encoded_token = torch.tensor(encoded_token).long()
            #         encoded_token = encoded_token.cuda()
            #         predict_sen = []
            #         for i in range(self.args.max_len):
            #             # print(encoded_token.size())
            #             outputs = self.model(input_ids=encoded_token)
            #             # print(outputs[0].shape)
            #             next_token_logits = outputs[0][0, -1, :]
            #             next_token_logits[self.tokenizer.convert_tokens_to_ids(
            #                 '[UNK]')] = -float('Inf')
            #             # new decoding fixing method due to unclear training data
            #             next_token = torch.argmax(next_token_logits).view(1)
            #             # tokenizer.sep_token_id 显示还没有被设定？？？
            #             if next_token == self.tokenizer.sep_token_id or i >= 20:
            #                 break
            #             predict_sen.append(next_token.item())
            #             encoded_token = torch.cat(
            #                 (encoded_token.view([-1]), next_token), dim=0).view([1, -1])

            #         text = self.tokenizer.convert_ids_to_tokens(predict_sen)
            #         result = ''
            #         for i in text:
            #             result += i
            #         result = jieba.cut(result, cut_all=False)
            #         result = [t for t in result]
            #         candidate_corpus.append(result)
            #     # now the score
            #     BLEUscore = bleu_score(
            #         candidate_corpus, self.valid_response, max_n=3, weights=[0.33, 0.33, 0.33])

            # # tensorboard record loss for each epoch
            # if self.tb_writer:
            #     self.tb_writer.add_scalar('Loss/train', np.mean(_loss), epoch)
            #     self.tb_writer.add_scalar(
            #         'Loss/validate', np.mean(valid_loss), epoch)
            #     self.tb_writer.add_scalar('BLEU/validate', BLEUscore, epoch)
            #     #self.tb_writer.add_scalar('Loss/train', sum(_loss)/len(dataloader), epoch)
            #     #self.tb_writer.add_scalar('Loss/validate', sum(valid_loss)/len(valid_dataloader), epoch)

            # # plot_record
            # # train_plot_record.append(np.mean(_loss)/len(dataloader))
            # # valid_plot_record.append(np.mean(valid_loss)/len(valid_dataloader))
            # train_plot_record.append(sum(_loss)/len(dataloader))
            # valid_plot_record.append(sum(valid_loss)/len(valid_dataloader))

            # if epoch % self.args.save_epoch == 0 and epoch > 0:
            #     model_save_path = './{}/model_epoch_{}'.format(
            #         parent_dir, str(epoch+1))
            #     if not os.path.exists(model_save_path):
            #         os.mkdir(model_save_path)
            #     model_to_save = self.model.module if hasattr(
            #         self.model, 'module') else self.model
            #     model_to_save.save_pretrained(model_save_path)

            #     # plot loss
            #     _y = train_plot_record
            #     _x = [i+1 for i in range(len(_y))]
            #     valid_y = valid_plot_record
            #     valid_x = [i+1 for i in range(len(valid_y))]
            #     plt.plot(_x, _y, label='train')
            #     plt.plot(valid_x, valid_y, label='valid')
            #     plt.xlabel('epoch')
            #     plt.ylabel('loss')
            #     plt.legend()
            #     plt.savefig(
            #         './{}/loss_epoch_{}'.format(parent_dir, str(epoch+1)))


def setup_logging(training_args):
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s -   %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=logging.INFO if is_main_process(
            training_args.local_rank) else logging.WARN,
    )

    # Log on each process the small summary:
    logger.warning(
        f"Process rank: {training_args.local_rank}, device: {training_args.device}, n_gpu: {training_args.n_gpu}"
        + f"distributed training: {bool(training_args.local_rank != -1)}, 16-bits training: {training_args.fp16}"
    )
    # Set the verbosity to info of the Transformers logger (on main process only):
    if is_main_process(training_args.local_rank):
        transformers.utils.logging.set_verbosity_info()
        transformers.utils.logging.enable_default_handler()
        transformers.utils.logging.enable_explicit_format()
    logger.info("Training/evaluation parameters %s", training_args)


def main():
    parser = HfArgumentParser((GPT2TrainingArguments, CollaborationArguments))
    training_args, collaboration_args = parser.parse_args_into_dataclasses()

    dialo = dialogpt(training_args)
    # make tokenize
    if training_args.make_tokenize:
        print('tokenizing raw data')
        dialo.tokenize_raw_data()
        print('tokenizing finished. Saved to {}'.format(
            training_args.saved_token_train))
        # tokenizing finished. Saved to gpt2/data/tokenized_train.csv

    logger.info(
        f"Found {len(collaboration_args.initial_peers)} initial peers: {collaboration_args.initial_peers}")
    if len(collaboration_args.initial_peers) == 0:
        raise ValueError(
            "Please specify at least one network endpoint in initial peers.")

    collaboration_args_dict = asdict(collaboration_args)
    setup_logging(training_args)

    # Set seed before initializing model.
    set_seed(training_args.seed)

    opt = dialo.get_opt()
    scheduler = dialo.get_scheduler(optimizer=opt)

    validators, local_public_key = metrics_utils.make_validators(
        collaboration_args_dict['experiment_prefix'])
    dht = hivemind.DHT(
        start=True, initial_peers=collaboration_args_dict.pop('initial_peers'),
        listen=not collaboration_args_dict['client_mode'],
        listen_on=collaboration_args_dict.pop('dht_listen_on'),
        endpoint=collaboration_args_dict.pop('endpoint'), record_validators=validators)

    total_batch_size_per_step = training_args.per_device_train_batch_size * \
        training_args.gradient_accumulation_steps
    statistics_expiration = collaboration_args_dict.pop(
        'statistics_expiration')
    adjusted_target_batch_size = collaboration_args_dict.pop('target_batch_size') \
        - collaboration_args_dict.pop('batch_size_lead')

    # input related to model:
    # 1. optimizer: opt
    # 2. scheduler
    collaborative_optimizer = hivemind.CollaborativeOptimizer(
        opt=opt, dht=dht, scheduler=scheduler, prefix=collaboration_args_dict.pop(
            'experiment_prefix'),
        compression_type=hivemind.utils.CompressionType.Value(
            collaboration_args_dict.pop('compression')),
        batch_size_per_step=total_batch_size_per_step, throughput=collaboration_args_dict.pop(
            'bandwidth'),
        target_batch_size=adjusted_target_batch_size, client_mode=collaboration_args_dict.pop(
            'client_mode'),
        verbose=True, start=True, **collaboration_args_dict
    )

    dialo.set_collaborative_opt(collaborative_optimizer)

    collaborative_call = CollaborativeCall(dht=dht, optimizer=collaborative_optimizer,
                                           model=dialo.get_model(), local_public_key=local_public_key,
                                           statistics_expiration=statistics_expiration)
    dialo.set_collaborative_call(collaborative_call)

    # start gpt2 training
    dialo.train()
    if dialo.tb_writer:
        dialo.tb_writer.close()


if __name__ == "__main__":
    main()
