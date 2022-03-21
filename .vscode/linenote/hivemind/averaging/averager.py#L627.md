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

