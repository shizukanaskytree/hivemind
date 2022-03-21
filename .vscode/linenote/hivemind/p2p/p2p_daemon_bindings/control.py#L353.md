Read response from the reader.


`hivemind/p2p/p2p_daemon_bindings/utils.py`

```py
async def write_pbmsg(stream: asyncio.StreamWriter, pbmsg: PBMessage) -> None:
    size = pbmsg.ByteSize()
    await write_unsigned_varint(stream, size)
    msg_bytes: bytes = pbmsg.SerializeToString()
    stream.write(msg_bytes)


async def read_pbmsg_safe(stream: asyncio.StreamReader, pbmsg: PBMessage) -> None:
    len_msg_bytes = await read_unsigned_varint(stream)
    msg_bytes = await stream.readexactly(len_msg_bytes)
    pbmsg.ParseFromString(msg_bytes)
```

