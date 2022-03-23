""" A background process that pull push your tensors with ps """

from __future__ import annotations

import asyncio
import contextlib
import ctypes
import multiprocessing as mp
import os
import random
import threading
import weakref
from dataclasses import asdict
from typing import Any, AsyncIterator, Dict, Optional, Sequence, Tuple, Union

import numpy as np
import torch

from hivemind.averaging.allreduce import AllreduceException, AllReduceRunner, AveragingMode, GroupID
from hivemind.averaging.control import AveragingStage, StepControl
from hivemind.averaging.group_info import GroupInfo
from hivemind.averaging.load_balancing import load_balance_peers
from hivemind.averaging.matchmaking import Matchmaking, MatchmakingException
from hivemind.averaging.partition import DEFAULT_PART_SIZE_BYTES
from hivemind.compression import (
    CompressionBase,
    CompressionInfo,
    NoCompression,
    deserialize_torch_tensor,
    serialize_torch_tensor,
)
from hivemind.dht import DHT, DHTID
from hivemind.p2p import P2P, P2PContext, P2PHandlerError, PeerID, ServicerBase
from hivemind.p2p.p2p_daemon_bindings.utils import ControlFailure, DispatchFailure
from hivemind.proto import averaging_pb2
from hivemind.utils import MPFuture, TensorDescriptor, get_logger
from hivemind.utils.asyncio import (
    achain,
    afirst,
    aiter_with_timeout,
    anext,
    as_aiter,
    azip,
    enter_asynchronously,
    switch_to_uvloop,
)
from hivemind.utils.grpc import combine_from_streaming, split_for_streaming
from hivemind.utils.serializer import MSGPackSerializer, SerializerBase
from hivemind.utils.timed_storage import DHTExpiration, ValueWithExpiration, get_dht_time

logger = get_logger(__name__)

# wxf: averaging -> optim folder.

# TODO:
# rpc_download_state

class ParameterServerService(mp.Process, ServicerBase):
    """
    Parameter Server service.

    :param dht: a DHT node that will be used to find groups
    :param start: if True, starts the background process immediately
    :param shutdown_timeout: when calling .shutdown, wait for up to this many seconds before terminating
    :param state_compression: a separate compression strategy for load_state_from_peers (default = no compression)
    """
    def __init__(
        self,
        dht: DHT,
        *,
        start: bool,
        shutdown_timeout: float = 5,
        state_compression: CompressionBase = NoCompression(),
        ):
        super().__init__()
        self.dht = dht
        self._inner_pipe, self._outer_pipe = mp.Pipe(duplex=True)  # a control pipe used to communicate with daemon
        self._ready = MPFuture()
        self.shutdown_timeout = shutdown_timeout
        self.state_compression = state_compression

        if start:
            self.run_in_background(await_ready=True)

    def run_in_background(self, await_ready: bool = True, timeout: Optional[float] = None) -> None:
        """
        Starts the worker service in a background process. if await_ready, this method will wait until background dht
        is ready to process incoming requests or for :timeout: seconds max.
        """
        self.start()
        if await_ready:
            self.wait_until_ready(timeout)

    def wait_until_ready(self, timeout: Optional[float] = None) -> None:
        self._ready.result(timeout=timeout)

    def run(self):
        """
        Run in a background thread; this is needed to avoid a heisenbug with broken OMP on fork
        Turns out, using a non-main thread creates a separate OMP pool that works even if the original pool is corrupted
        Read more: https://github.com/pytorch/pytorch/issues/17199
        """
        thread = threading.Thread(target=self._run_internal, daemon=True)
        thread.start()
        thread.join()

    def _run_internal(self):
        """Serve this worker service forever. This function will not return until the worker service is shut down"""
        loop = switch_to_uvloop()
        # initialize asyncio synchronization primitives in this event loop

        pipe_semaphore = asyncio.Semaphore(value=0)
        loop.add_reader(self._inner_pipe.fileno(), pipe_semaphore.release)

        async def _run():
            try:
                self._p2p = await self.dht.replicate_p2p()
                await self.add_p2p_handlers(self._p2p)
            except Exception as e:
                # Loglevel is DEBUG since normally the exception is propagated to the caller
                logger.debug(e, exc_info=True)
                self._ready.set_exception(e)
                return
            self._ready.set_result(None)

            while True:
                try:
                    await asyncio.wait_for(pipe_semaphore.acquire(), timeout=self.request_timeout)
                except asyncio.TimeoutError:
                    pass
                if not self._inner_pipe.poll():
                    continue
                try:
                    method, args, kwargs = self._inner_pipe.recv()
                except (OSError, ConnectionError, RuntimeError) as e:
                    logger.exception(e)
                    await asyncio.sleep(self.request_timeout)
                    continue
                task = asyncio.create_task(getattr(self, method)(*args, **kwargs))
                if method == "_shutdown":
                    await task
                    break

        loop.run_until_complete(_run())

    async def rpc_download_state(
        self, _request: averaging_pb2.DownloadRequest, _context: P2PContext
    ) -> AsyncIterator[averaging_pb2.DownloadData]:
        """
        Get the up-to-date parameter server state.
        The state consists of two parts: (serialized_metadata, tensors)

         - serialized_metadata is a small serialized bytestring meant to store scalars and hyperparameters
         - tensors is a sequence of pytorch tensors that represent model parameters or optimizer statistics
        """
        metadata, tensors, infos = await self._get_current_state_from_host_process()
        if infos is None:
            infos = [CompressionInfo.from_tensor(tensor, key=i) for i, tensor in enumerate(tensors)]
        assert len(tensors) == len(infos)

        for tensor, info in zip(tensors, infos):
            for part in split_for_streaming(self.state_compression.compress(tensor, info, allow_inplace=False)):
                if metadata is not None:
                    yield averaging_pb2.DownloadData(tensor_part=part, metadata=metadata)
                    metadata = None
                else:
                    yield averaging_pb2.DownloadData(tensor_part=part)
