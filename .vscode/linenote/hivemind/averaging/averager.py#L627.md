这个是 stub call 的 server function `rpc_download_state`.

## server side

```
yield averaging_pb2.DownloadData(tensor_part=part, metadata=metadata)
```

## client side

```py
try:
    stub = self.get_stub(self._p2p, peer, namespace=self.prefix)
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
```

# check being called by client stub

a trainer as a server, server side log: https://gist.github.com/shizukanaskytree/48019c9c3fa95663324723db2f8ff435

```py
async def rpc_download_state(
        self, _request: averaging_pb2.DownloadRequest, _context: P2PContext
    ) -> AsyncIterator[averaging_pb2.DownloadData]:
        """
        Get the up-to-date trainer state from a peer.
        The state consists of two parts: (serialized_metadata, tensors)

         - serialized_metadata is a small serialized bytestring meant to store scalars and hyperparameters
         - tensors is a sequence of pytorch tensors that represent model parameters or optimizer statistics
        """
        logger.info('calling rpc_download_state')
        if not self.allow_state_sharing:
            return  # deny request and direct peer to the next prospective averager
        metadata, tensors, infos = await self._get_current_state_from_host_process()
        if infos is None:
            infos = [CompressionInfo.from_tensor(tensor, key=i) for i, tensor in enumerate(tensors)]
        assert len(tensors) == len(infos)

        for tensor, info in zip(tensors, infos):
            for part in split_for_streaming(self.state_compression.compress(tensor, info, allow_inplace=False)):
                if metadata is not None:
                    yield averaging_pb2.DownloadData(tensor_part=part, metadata=metadata)
                    metadata = None
                    logger.info('for loop iterating part in rpc_download_state: part + metadata')
                else:
                    logger.info('for loop iterating part in rpc_download_state: part')
                    yield averaging_pb2.DownloadData(tensor_part=part)
        logger.info('called rpc_download_state')
```