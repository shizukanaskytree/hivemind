# Code

```py
    async def _communicate_with_peer(self, peer_id: PeerID):
        """Send a part of local tensors and metadata to a single peer, receive the average for that part of tensors"""
        peer_index = self.ordered_peer_ids.index(peer_id)
        if peer_id == self.peer_id:
            sender_index = self.sender_peer_ids.index(peer_id)
            for part_index, tensor_part in enumerate(self.parts_for_local_averaging):
                averaged_part = await self.tensor_part_reducer.accumulate_part(
                    sender_index, part_index, tensor_part, weight=self.weight
                )
                self.tensor_part_container.register_processed_part(peer_index, part_index, averaged_part - tensor_part)

        else:
            try:
                done_sending = asyncio.Event()
                inputs_aiter = attach_event_on_finished(self._generate_input_for_peer(peer_index), done_sending)
                stream = await self._get_peer_stub(peer_id).rpc_aggregate_part(inputs_aiter)

                if self.should_delay_results(self.peer_id):
                    await done_sending.wait()

                part_index = 0

                def _try_deserialize(msg):
                    if msg.code != averaging_pb2.AVERAGED_PART:
                        raise AllreduceException(f"{peer_id} sent {averaging_pb2.MessageCode.Name(msg.code)}")
                    return deserialize_torch_tensor(msg.tensor_part), msg

                async for delta, msg in amap_in_executor(
                    _try_deserialize,
                    aiter_with_timeout(stream, self.reducer_timeout),
                    max_prefetch=self.tensor_part_container.prefetch,
                ):
                    self.tensor_part_container.register_processed_part(peer_index, part_index, delta)
                    part_index += 1

                if part_index != self.tensor_part_container.num_parts_by_peer[peer_index]:
                    raise AllreduceException(
                        f"peer {peer_id} sent {part_index} parts, but we expected "
                        f"{self.tensor_part_container.num_parts_by_peer[peer_index]}"
                    )
            except BaseException as e:
                if isinstance(e, Exception):
                    logger.debug(f"Caught {repr(e)} when communicating to {peer_id}", exc_info=True)
                self.tensor_part_container.register_failed_reducer(peer_index)
                raise
```

# 道

Send a part of local tensors and metadata to a single peer, receive the average for that part of tensors.

asyncio 好难.

# 取需要

目标: Send a part of local tensors and metadata to the parameter server, receive nothing.

# call stack

Thread-15:

```
_communicate_with_peer (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/allreduce.py:205)
_run_internal (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:339)
run (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:870)
_bootstrap_inner (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:932)
_bootstrap (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:890)
_communicate_with_peer (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/allreduce.py:205)
_run_internal (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:339)
run (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:870)
_bootstrap_inner (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:932)
_bootstrap (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:890)
```

# 逐行分析

# LOC

```
    async def _communicate_with_peer(self, peer_id: PeerID):
```

分析:

```
    :param peer_id: your peer_id, must be included in ordered_peer_ids
```

`PeerID`
```
hivemind/p2p/p2p_daemon_bindings/datastructures.py
```

`peer_id`

```
peer_id
<libp2p.peer.id.ID (QmfLoigam7oC8BrT3PqLAm3aBGRfaX2bZwHY2DBvbLK5AV)>
```

展开 `peer_id`

```
peer_id

<libp2p.peer.id.ID (QmfLoigam7oC8BrT3PqLAm3aBGRfaX2bZwHY2DBvbLK5AV)>

special variables:
function variables:

xor_id: 87747356964959318668804444745885361357725677310674981095844001316534094855514
_b58_str: 'QmfLoigam7oC8BrT3PqLAm3aBGRfaX2bZwHY2DBvbLK5AV'
_bytes: b'\x12 \xfc\xa0\xdd\x85\xb8\xe0\xc4>i[<\x13\\CW\x8f5\xc8\xc2\x17\xd1d\xa0\xaf\xf8\xfa<\xf7\x88h\x1b6'
_xor_id: 87747356964959318668804444745885361357725677310674981095844001316534094855514
```

结构体来自

```py
hivemind/p2p/p2p_daemon_bindings/datastructures.py

class PeerID:
    def __init__(self, peer_id_bytes: bytes) -> None:
        self._bytes = peer_id_bytes
        self._xor_id = int(sha256_digest(self._bytes).hex(), 16)
        self._b58_str = base58.b58encode(self._bytes).decode()

    @property
    def xor_id(self) -> int:
        return self._xor_id

    def to_bytes(self) -> bytes:
        return self._bytes

    def to_base58(self) -> str:
        return self._b58_str

    def __repr__(self) -> str:
        return f"<libp2p.peer.id.ID ({self.to_base58()})>"

    def __str__(self):
        return self.to_base58()

    def pretty(self):
        return self.to_base58()

    def to_string(self):
        return self.to_base58()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.to_base58() == other
        elif isinstance(other, bytes):
            return self._bytes == other
        elif isinstance(other, PeerID):
            return self._bytes == other._bytes
        else:
            return False

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PeerID):
            raise TypeError(f"'<' not supported between instances of 'PeerID' and '{type(other)}'")

        return self.to_base58() < other.to_base58()

    def __hash__(self) -> int:
        return hash(self._bytes)

    @classmethod
    def from_base58(cls, base58_id: str) -> "PeerID":
        peer_id_bytes = base58.b58decode(base58_id)
        return cls(peer_id_bytes)
```

尝试了 `peer_id.to_base58()`:

```
peer_id.to_base58()
'QmfLoigam7oC8BrT3PqLAm3aBGRfaX2bZwHY2DBvbLK5AV'
```



# LOC

```
        peer_index = self.ordered_peer_ids.index(peer_id)
```

关于 `ordered_peer_ids`:

```
    :param ordered_peer_ids: group peer_ids ordered s.t. i-th peer_id is responsible for averaging i-th part
```


```
self.ordered_peer_ids
```

is from


```
class AllReduceRunner(ServicerBase):
    def __init__(
        ordered_peer_ids: Sequence[PeerID],
    )

        self.group_id, self.ordered_peer_ids = group_id, ordered_peer_ids
```

打印:

```
self.ordered_peer_ids
(<libp2p.peer.id.ID (...d7zLNxFA)>, <libp2p.peer.id.ID (...BvbLK5AV)>)
special variables:
function variables:
0: <libp2p.peer.id.ID (QmP6UxemVbNXYgLTw64cUWpbX5HdpFdHF6Tjahd7zLNxFA)>
1: <libp2p.peer.id.ID (QmfLoigam7oC8BrT3PqLAm3aBGRfaX2bZwHY2DBvbLK5AV)>
len(): 2
```

打印:

```
peer_index
1
```

# LOC

```
        if peer_id == self.peer_id:
```

打印:

```
peer_id
<libp2p.peer.id.ID (QmfLoigam7oC8BrT3PqLAm3aBGRfaX2bZwHY2DBvbLK5AV)>
```

```
self.peer_id
<libp2p.peer.id.ID (QmfLoigam7oC8BrT3PqLAm3aBGRfaX2bZwHY2DBvbLK5AV)>
```

they are equal!


# LOC

```
            sender_index = self.sender_peer_ids.index(peer_id)
```

`self.sender_peer_ids`

```
self.sender_peer_ids

[<libp2p.peer.id.ID (...d7zLNxFA)>, <libp2p.peer.id.ID (...BvbLK5AV)>]

special variables:
function variables:

0: <libp2p.peer.id.ID (QmP6UxemVbNXYgLTw64cUWpbX5HdpFdHF6Tjahd7zLNxFA)>
1: <libp2p.peer.id.ID (QmfLoigam7oC8BrT3PqLAm3aBGRfaX2bZwHY2DBvbLK5AV)>

len(): 2
```

`self.sender_peer_ids` 来自

```py
class AllReduceRunner(ServicerBase):
    def __init__(...):

        self.sender_peer_ids = []
        for peer_id, mode in zip(self.ordered_peer_ids, modes):
            if mode != AveragingMode.AUX:
                self.sender_peer_ids.append(peer_id)

```

粗略来说: `self.ordered_peer_ids` 等于 `self.sender_peer_ids`.

打印结果:

```
sender_index
1
```


# LOC

```
            for part_index, tensor_part in enumerate(self.parts_for_local_averaging):
```


```
self.parts_for_local_averaging
```
来自

```
class AllReduceRunner(ServicerBase):
    def __init__(...):

        self.parts_for_local_averaging = self.tensor_part_container.get_raw_input_parts(peer_id_index)
```

# get data from other peers

code:
```
stream = await self._get_peer_stub(peer_id).rpc_aggregate_part(inputs_aiter)
```

code:

```py
try:
    done_sending = asyncio.Event()
    inputs_aiter = attach_event_on_finished(self._generate_input_for_peer(peer_index), done_sending)
    stream = await self._get_peer_stub(peer_id).rpc_aggregate_part(inputs_aiter)

    if self.should_delay_results(self.peer_id):
        await done_sending.wait()

    part_index = 0

    def _try_deserialize(msg):
        if msg.code != averaging_pb2.AVERAGED_PART:
            raise AllreduceException(f"{peer_id} sent {averaging_pb2.MessageCode.Name(msg.code)}")
        return deserialize_torch_tensor(msg.tensor_part), msg

    async for delta, msg in amap_in_executor(
        _try_deserialize,
        aiter_with_timeout(stream, self.reducer_timeout),
        max_prefetch=self.tensor_part_container.prefetch,
    ):
        self.tensor_part_container.register_processed_part(peer_index, part_index, delta)
        part_index += 1

    if part_index != self.tensor_part_container.num_parts_by_peer[peer_index]:
        raise AllreduceException(
            f"peer {peer_id} sent {part_index} parts, but we expected "
            f"{self.tensor_part_container.num_parts_by_peer[peer_index]}"
        )
except BaseException as e:
    if isinstance(e, Exception):
        logger.debug(f"Caught {repr(e)} when communicating to {peer_id}", exc_info=True)
    self.tensor_part_container.register_failed_reducer(peer_index)
    raise

```



# rpc_aggregate_part

```
hivemind/averaging/allreduce.py:261:
async def rpc_aggregate_part
```

```
hivemind/averaging/averager.py:581:
async def rpc_aggregate_part(
```


# Ref

    An internal class that runs butterfly AllReduce in a predefined group of averagers.



===