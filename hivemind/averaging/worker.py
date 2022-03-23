
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

from hivemind.p2p import P2P, P2PContext, P2PHandlerError, PeerID, ServicerBase
from hivemind.utils import MPFuture, TensorDescriptor, get_logger
from hivemind.dht import DHT, DHTID
from hivemind.utils.timed_storage import DHTExpiration, ValueWithExpiration, get_dht_time

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
from hivemind.proto import averaging_pb2
from hivemind.utils.grpc import combine_from_streaming, split_for_streaming
from hivemind.compression import (
    CompressionBase,
    CompressionInfo,
    NoCompression,
    deserialize_torch_tensor,
    serialize_torch_tensor,
)

logger = get_logger(__name__)

class WorkerService(mp.Process, ServicerBase):
    """ Worker's service. It is like gRPC.

    :param dht: a DHT node that will be used to find groups
    :param start: if True, starts the background process immediately
    :param shutdown_timeout: when calling .shutdown, wait for up to this many seconds before terminating


    Example:

    >>> worker_service = WorkerService(...)
    >>> with worker_service.get_tensors() as tensors:
    >>>     # run some code, modify tensors if necessary
    >>>     tensors[0] += 1
    >>> # do not use tensors after the lock is released
    >>> metadata = worker_service.step(gather=dict(my_batch_size=32))
    >>> # run averaging once (in-place), gather metadata from groupmates
    >>> with worker_service.get_tensors() as tensors_after_averaging:
    >>>     pass # use the averaged tensors
    """

    _p2p: P2P

    def __init__(
        self,
        dht: DHT,
        *,
        start: bool,
        shutdown_timeout: float = 5,
        ):
        super().__init__()
        self.dht = dht
        self._inner_pipe, self._outer_pipe = mp.Pipe(duplex=True)  # a control pipe used to communicate with daemon
        self._ready = MPFuture()
        self.shutdown_timeout = shutdown_timeout

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

    def load_state_from_ps(
        self, wait: bool = True, timeout: Optional[float] = None
    ) -> Optional[Tuple[Any, Sequence[torch.Tensor]]]:
        """
        Try to download the latest optimizer state one of the existing ps.
        :returns: on success, return a 2-tuple with (metadata, tensors), where

        - metadata is a small object containing metadata (e.g. hyperparameters, scalars, etc)
        - tensors is a sequence of pytorch tensors meant to contain peer's model weights and optimizer statistics

        The exact contents of both metadata and tensors are determined by get_current_state method

        Example:
        >>> loaded_state = load_state_from_ps(**kwargs)
        """
        future = MPFuture()
        self._outer_pipe.send(("_load_state_from_ps", [], dict(timeout=timeout, future=future)))
        return future.result(timeout=timeout) if wait else future

    async def _load_state_from_ps(self, future: MPFuture, timeout: Optional[float] = None):
        if timeout is not None:
            timeout = 3.0 # hardcode # self.next_chunk_timeout if self.next_chunk_timeout is not None else self.request_timeout
        try:
            # 根据 key "ps" 找到对应的 peer id
            # 下面的如果不改, 可以理解成几个 parameter server
            peer_priority, _ = self.dht.get("ps", latest=True) or ({}, None)
            peer_priority = {
                PeerID(peer_id): (float(info.value), random.random())  # using randomness as a tie breaker
                for peer_id, info in peer_priority.items()
                if isinstance(info, ValueWithExpiration) and isinstance(info.value, (float, int))
            }

            if not isinstance(peer_priority, dict) or len(peer_priority) == 0:
                logger.info(f"worker_service could not load state from peers: peer dict empty or corrupted {peer_priority}")
                future.set_result(None)
                return

            metadata = None
            for peer in sorted(peer_priority.keys(), key=peer_priority.get, reverse=True):
                if peer != self.peer_id:
                    logger.info(f"Downloading parameters from peer {peer}")
                    try:
                        stub = self.get_stub(self._p2p, peer, namespace=self.prefix)
                        # 借用一下吧
                        stream = await stub.rpc_download_state(averaging_pb2.DownloadRequest())
                        current_tensor_parts, tensors = [], []

                        async for message in aiter_with_timeout(stream, timeout=timeout):
                            if message.metadata:
                                metadata = self.serializer.loads(message.metadata)
                            if message.tensor_part.dtype and current_tensor_parts:
                                # tensor_part.dtype indicates the start of the new tensor, so we should wrap up this one
                                tensors.append(deserialize_torch_tensor(combine_from_streaming(current_tensor_parts)))
                                current_tensor_parts = []
                            current_tensor_parts.append(message.tensor_part)
                        if current_tensor_parts:
                            tensors.append(deserialize_torch_tensor(combine_from_streaming(current_tensor_parts)))

                        if not metadata:
                            logger.debug(f"Peer {peer} did not send its state")
                            continue

                        logger.info(f"Finished downloading state from {peer}")
                        future.set_result((metadata, tensors))
                        return
                    except Exception as e:
                        logger.exception(f"Failed to download state from {peer} - {repr(e)}")

        finally:
            if not future.done():
                future.set_result(None)


    def shutdown(self) -> None:
        """Shut down the worker_service process"""
        if self.is_alive():
            self._outer_pipe.send(("_shutdown", [self.shutdown_timeout], {}))  # shut down the daemon process
            self._inner_pipe.send(("_SHUTDOWN", None))  # shut down background thread in master
            self.join(self.shutdown_timeout)
            if self.is_alive():
                logger.warning("worker_service did not shut down within the grace period; terminating it the hard way")
                self.terminate()
        else:
            logger.exception("worker_service shutdown has no effect: the process is already not alive")

    async def _shutdown(self, timeout: Optional[float]) -> None:
        remaining_tasks = set()
        for group in self._running_groups.values():
            remaining_tasks.update(group.finalize(cancel=True))
        await asyncio.wait_for(asyncio.gather(*remaining_tasks), timeout)

    def __del__(self):
        if self._parent_pid == os.getpid() and self.is_alive():
            self.shutdown()