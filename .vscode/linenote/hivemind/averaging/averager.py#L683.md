另一个线程引起这个线程.
另一个线程是

```py
    def load_state_from_peers(self, **kwargs):
        """
        Attempt to load the newest collaboration state from other peers within the same run_id.

        If successful, this will update parameters, optimizer state, local epoch and learning rate schedule in-place.
        """
        # note: we tag along for the next all-reduce because the run may have already started and cancelling it
        # will cause peers to restart matchmaking and may  stall the entire collaboration for a few seconds.
        if self.scheduled_grads is not None and not self.scheduled_grads.done():
            self._tag_along_with_zero_weight(self.scheduled_grads)
            self.scheduled_grads = None
        self.state_averager.step(wait_for_delayed_updates=True)

        with self.tracker.pause_updates():
            while True:
                try:
                    self.state_averager.load_state_from_peers(timeout=self.load_state_timeout, **kwargs)
                    break
                except KeyboardInterrupt:
                    raise
                except BaseException as e:
                    logger.exception(f"Failed to load state from peers: {e}, retrying ...")
                    continue

```



```
key_manager = self._matchmaking.group_key_manager
```


```
self._matchmaking
Matchmaking(peer_id=QmTVyNRCvr3nfzDeAicnF8zz16oEFooih6HgNexF4o7pxD, schema=154...b'\x9b\xf3\x9a\x00V\xd0[\xf1', not looking for group, current key = albert_state_averager.0b, client_mode=False)
```

```
key_manager
<hivemind.averaging.key_manager.GroupKeyManager object at 0x7f0c9659ad00>
```


```py
peer_priority, _ = self.dht.get(f"{key_manager.prefix}.all_averagers", latest=True) or ({}, None)
```

```
key_manager.prefix
'albert_state_averager'
```



```
peer_priority

{b'\x12 \xf0]\xc4\xdcN\x17\xd9;\xff&+\xee,\xef\x9b\x0c\xcak...\xbf\xbbO\x0b{6\x9d\xc9\x80\xbd': ValueWithExpiration(...7.6244023), b'\x12 b\x82~4\xfe?\x80\xdc\x88\xe5\xb41i\x81\xe1\xf5\x95\x04...Tp\xf3yR\xae\x10\xb8\xe8/': ValueWithExpiration(...0.2098484)}
special variables:
function variables:

b'\x12 \xf0]\xc4\xdcN\x17\xd9;\xff&+\xee,\xef\x9b\x0c\xcak_\x06\x13w\xbf\xbbO\x0b{6\x9d\xc9\x80\xbd': ValueWithExpiration(value=3933.0, expiration_time=1647814697.6244023)
b'\x12 b\x82~4\xfe?\x80\xdc\x88\xe5\xb41i\x81\xe1\xf5\x95\x04\xee\xf9\xa90Tp\xf3yR\xae\x10\xb8\xe8/': ValueWithExpiration(value=0.0, expiration_time=1647814700.2098484)

len(): 2
```



```py
peer_priority = {
    PeerID(peer_id): (float(info.value), random.random())  # using randomness as a tie breaker
    for peer_id, info in peer_priority.items()
    if isinstance(info, ValueWithExpiration) and isinstance(info.value, (float, int))
}
```


```py
peer_priority.items()
dict_items(
[(b'\x12 \xf0]\xc4\xdcN\x17\xd9;\xff&+\xee,\xef\x9b\x0c\xcak_\x06\x13w\xbf\xbbO\x0b{6\x9d\xc9\x80\xbd', ValueWithExpiration(value=3933.0, expiration_time=1647814697.6244023)), (b'\x12 b\x82~4\xfe?\x80\xdc\x88\xe5\xb41i\x81\xe1\xf5\x95\x04\xee\xf9\xa90Tp\xf3yR\xae\x10\xb8\xe8/', ValueWithExpiration(value=0.0, expiration_time=1647814700.2098484))])
```


```
peer_priority
{<libp2p.peer.id.ID (...mj2Lvqe4)>: (3933.0, 0.2548711064567245), <libp2p.peer.id.ID (...GYTXikFp)>: (0.0, 0.9160918253901406)}

special variables:
function variables:

<libp2p.peer.id.ID (QmeWwVBjrK1H8dYHxZyKvDngJiKG1FgKZwpFHemj2Lvqe4)>: (3933.0, 0.2548711064567245)
<libp2p.peer.id.ID (QmUyC5ARzR7Y3RPg2UPjz1jb8pZHxb6BBVbVB3GYTXikFp)>: (0.0, 0.9160918253901406)
len(): 2
```


# LOC

```py
metadata = None
for peer in sorted(peer_priority.keys(), key=peer_priority.get, reverse=True):
    if peer != self.peer_id:
        #-------------------

        logger.info(f"Downloading parameters from peer {peer}")
        try:
            stub = self.get_stub(self._p2p, peer, namespace=self.prefix)
            stream = await stub.rpc_download_state(averaging_pb2.DownloadRequest())
            current_tensor_parts, tensors = [], []

```


```
Mar 20 15:24:14.045 [INFO] Downloading parameters from peer QmeWwVBjrK1H8dYHxZyKvDngJiKG1FgKZwpFHemj2Lvqe4
```


```
peer
<libp2p.peer.id.ID (QmeWwVBjrK1H8dYHxZyKvDngJiKG1FgKZwpFHemj2Lvqe4)>
```

```
self._p2p
<hivemind.p2p.p2p_daemon.P2P object at 0x7f0c9659afd0>
```

```
self.prefix
'albert_state_averager'
```


# LOC

```py
class ServicerBase:

    @classmethod
    def get_stub(cls, p2p: P2P, peer: PeerID, *, namespace: Optional[str] = None) -> StubBase:
        cls._collect_rpc_handlers()
        return cls._stub_type(p2p, peer, namespace)
```

```py
cls._stub_type(p2p, peer, namespace)
```

```py
namespace
'albert_state_averager'
peer
<libp2p.peer.id.ID (QmeWwVBjrK1H8dYHxZyKvDngJiKG1FgKZwpFHemj2Lvqe4)>
p2p
<hivemind.p2p.p2p_daemon.P2P object at 0x7f0c9659afd0>
```

[see _collect_rpc_handlers](.vscode/linenote/hivemind/p2p/servicer.py#L49.md)


# LOC

```py
stub = self.get_stub(self._p2p, peer, namespace=self.prefix)
```

```
stub
<hivemind.p2p.servicer.TrainingStateAveragerStub object at 0x7f0d115a2f70>
```

[see _collect_rpc_handlers again](.vscode/linenote/hivemind/p2p/servicer.py#L49.md)


# `_make_rpc_caller`

不可思议的跳转:

```
to : caller (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/servicer.py:93)
from : _load_state_from_peers (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:706)

_run_internal (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:339)
run (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:870)
_bootstrap_inner (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:932)
_bootstrap (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:890)
```


```py
    @classmethod
    def _make_rpc_caller(cls, handler: RPCHandler):
        input_type = AsyncIterator[handler.request_type] if handler.stream_input else handler.request_type
        output_type = AsyncIterator[handler.response_type] if handler.stream_output else handler.response_type

        # This method will be added to a new Stub type (a subclass of StubBase)
        async def caller(self: StubBase, input: input_type, timeout: Optional[float] = None) -> output_type:
            # ----------

            handle_name = cls._get_handle_name(self._namespace, handler.method_name)
            if not handler.stream_output:
                return await asyncio.wait_for(
                    self._p2p.call_protobuf_handler(self._peer, handle_name, input, handler.response_type),
                    timeout=timeout,
                )

            if timeout is not None:
                raise ValueError("Timeouts for handlers returning streams are not supported")
            return await self._p2p.iterate_protobuf_handler(self._peer, handle_name, input, handler.response_type)

        caller.__name__ = handler.method_name
        return caller

```

```py
self._namespace
'albert_state_averager'


handler.method_name
'rpc_download_state'
```


call:


```py
    @classmethod
    def _get_handle_name(cls, namespace: Optional[str], method_name: str) -> str:
        handle_name = f"{cls.__name__}.{method_name}"
        if namespace is not None:
            handle_name = f"{namespace}::{handle_name}"
        return handle_name
```

LOC:

```
handle_name = f"{cls.__name__}.{method_name}"
```

output

```
handle_name
'TrainingStateAverager.rpc_download_state'
```

LOC:
```
handle_name = f"{namespace}::{handle_name}"
```

```
handle_name
'albert_state_averager::TrainingStateAverager.rpc_download_state'
```

# _make_rpc_caller

```py
    @classmethod
    def _make_rpc_caller(cls, handler: RPCHandler):
        input_type = AsyncIterator[handler.request_type] if handler.stream_input else handler.request_type
        output_type = AsyncIterator[handler.response_type] if handler.stream_output else handler.response_type

        # This method will be added to a new Stub type (a subclass of StubBase)
        async def caller(self: StubBase, input: input_type, timeout: Optional[float] = None) -> output_type:
            handle_name = cls._get_handle_name(self._namespace, handler.method_name)
            # ----------------------------------- start fromm here


            # 未进入
            if not handler.stream_output:
                return await asyncio.wait_for(
                    self._p2p.call_protobuf_handler(self._peer, handle_name, input, handler.response_type),
                    timeout=timeout,
                )

            # 未进入
            if timeout is not None:
                raise ValueError("Timeouts for handlers returning streams are not supported")


            return await self._p2p.iterate_protobuf_handler(self._peer, handle_name, input, handler.response_type)

        caller.__name__ = handler.method_name
        return caller
```

```
handle_name
'albert_state_averager::TrainingStateAverager.rpc_download_state'
```


LOC

```
return await self._p2p.iterate_protobuf_handler(
    self._peer,
    handle_name,
    input,
    handler.response_type
)
```

# `iterate_protobuf_handler` go to `hivemind/p2p/p2p_daemon.py`

```py
class P2P:
    """
    This class is responsible for establishing peer-to-peer connections through NAT and/or firewalls.
    It creates and manages a libp2p daemon (https://libp2p.io) in a background process,
    then terminates it when P2P is shut down. In order to communicate, a P2P instance should
    either use one or more initial_peers that will connect it to the rest of the swarm or
    use the public IPFS network (https://ipfs.io).

    For incoming connections, P2P instances add RPC handlers that may be accessed by other peers:
      - `P2P.add_protobuf_handler` accepts a protobuf message and returns another protobuf
      - `P2P.add_binary_stream_handler` transfers raw data using bi-directional streaming interface

    To access these handlers, a P2P instance can `P2P.call_protobuf_handler`/`P2P.call_binary_stream_handler`,
    using the recipient's unique `P2P.peer_id` and the name of the corresponding handler.
    """

    async def iterate_protobuf_handler(
        self,
        peer_id: PeerID,
        name: str,
        input: Union[TInputProtobuf, TInputStream],
        output_protobuf_type: Type[Message],
    ) -> TOutputStream:
        requests = input if isinstance(input, AsyncIterableABC) else as_aiter(input)
        return await self._iterate_protobuf_stream_handler(peer_id, name, requests, output_protobuf_type)
```


```
peer_id
<libp2p.peer.id.ID (QmeWwVBjrK1H8dYHxZyKvDngJiKG1FgKZwpFHemj2Lvqe4)>


name
'albert_state_averager::TrainingStateAverager.rpc_download_state'


output_protobuf_type
<class 'averaging_pb2.DownloadData'>
```


input 是一个 空的 request.
```
input

special variables:
function variables:

DESCRIPTOR: <google.protobuf.pyext._message.MessageDescriptor object at 0x7f0bfa899d60>
Extensions: 'Traceback (most recent call last):\n  File "/home/wxf/anaconda3/envs/hm_master/lib/python3.8/site-packages/debugpy/_vendored/pydevd/_pydevd_bundle/pydevd_resolver.py", line 193, in _get_py_dictionary\n    attr = getattr(var, name)\nAttributeError: Extensions\n'
_CheckCalledFromGeneratedFile: <built-in method _CheckCalledFromGeneratedFile of google.protobuf.pyext._message.MessageMeta object at 0x7f0bfba35580>
_SetListener: <bound method Message._SetListener of >
_extensions_by_name: {}
_extensions_by_number: {}
```


```
type(input)
<class 'averaging_pb2.DownloadRequest'>
```


LOC:

```py
requests = input if isinstance(input, AsyncIterableABC) else as_aiter(input)
```




# `iterate_protobuf_handler` call `_iterate_protobuf_stream_handler`


```

```

# `_iterate_protobuf_stream_handler` <- `_iterate_protobuf_stream_handler`

```py
_iterate_protobuf_stream_handler (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/p2p_daemon.py:387)
iterate_protobuf_handler (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/p2p_daemon.py:509)
caller (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/servicer.py:102)
_load_state_from_peers (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:706)
_run_internal (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:339)
run (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:870)
_bootstrap_inner (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:932)
_bootstrap (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:890)
```


```py
    async def _iterate_protobuf_stream_handler(
        self, peer_id: PeerID, name: str, requests: TInputStream, output_protobuf_type: Type[Message]
    ) -> TOutputStream:
        _, reader, writer = await self.call_binary_stream_handler(peer_id, name)

```


```
peer_id
<libp2p.peer.id.ID (QmeWwVBjrK1H8dYHxZyKvDngJiKG1FgKZwpFHemj2Lvqe4)>


name
'albert_state_averager::TrainingStateAverager.rpc_download_state'


requests
<async_generator object as_aiter at 0x7f0d142ca550>


output_protobuf_type
<class 'averaging_pb2.DownloadData'>
```

LOC:

```
        _, reader, writer = await self.call_binary_stream_handler(peer_id, name)
```











===