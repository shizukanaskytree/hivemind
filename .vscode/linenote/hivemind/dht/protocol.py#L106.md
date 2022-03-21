# Code

```py
class DHTProtocol(ServicerBase):

    async def call_ping(self, peer: PeerID, validate: bool = False, strict: bool = True) -> Optional[DHTID]:
        """
        Get peer's node id and add him to the routing table. If peer doesn't respond, return None
        :param peer: peer ID to ping
        :param validate: if True, validates that node's peer_id is available
        :param strict: if strict=True, validation will raise exception on fail, otherwise it will only warn
        :note: if DHTProtocol was created with client_mode=False, also request peer to add you to his routing table

        :return: node's DHTID, if peer responded and decided to send his node_id
        """
        try:
            async with self.rpc_semaphore:
                ping_request = dht_pb2.PingRequest(peer=self.node_info, validate=validate)
                time_requested = get_dht_time()

                response = await self.get_stub(peer).rpc_ping(ping_request, timeout=self.wait_timeout)
                # ------------------------------------------------------------------------------------

                time_responded = get_dht_time()
```

# 道

Call p2p rpc by entering a series of wrapped functions. 因为需要 authentification, 所以就 wrap 一下 function.
`rpc_ping` is converted by `wrapped_rpc` in `hivemind/utils/auth.py`

# 法

```py
response = await self.get_stub(peer).rpc_ping(ping_request, timeout=self.wait_timeout)
```

# 实例化

## inputs

```py
ping_request

peer {
  node_id: "m\207r\tn\366On\364R\323\220\023\202\263V\347\227n\304"
}
validate: true
special variables:
function variables:
DESCRIPTOR: <google.protobuf.pyext._message.MessageDescriptor object at 0x7f5b0e44a580>
Extensions: 'Traceback (most recent call last):\n  File "/home/wxf/anaconda3/envs/hm_master/lib/python3.8/site-packages/debugpy/_vendored/pydevd/_pydevd_bundle/pydevd_resolver.py", line 193, in _get_py_dictionary\n    attr = getattr(var, name)\nAttributeError: Extensions\n'
auth:
peer: node_id: "m\207r\tn\366On\364R\323\220\023\202\263V\347\227n\304"
validate: True
_CheckCalledFromGeneratedFile: <built-in method _CheckCalledFromGeneratedFile of google.protobuf.pyext._message.MessageMeta object at 0x7f5bb0b22580>
_SetListener: <bound method Message._SetListener of peer {
  node_id: "m\207r\tn\366On\364R\323\220\023\202\263V\347\227n\304"
}
validate: true
>
_extensions_by_name: {}
_extensions_by_number: {}
```

```py
self.wait_timeout
3
```

## 调用过程

因为 `self.get_stub(peer)` 返回的是 `class AuthRPCWrapper`

因为 xxx.yyy 的过程就是 call 了 `class AuthRPCWrapper: __getattribute__` (`hivemind/utils/auth.py`).

`self.get_stub(peer).rpc_ping` will invoke `__getattribute__ (/home/wxf/hm_prj/hm_master/hivemind/hivemind/utils/auth.py:191)`

see call stack:

```py
__getattribute__ (/home/wxf/hm_prj/hm_master/hivemind/hivemind/utils/auth.py:191)
call_ping (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/protocol.py:106)
run (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/dht.py:134)
_bootstrap (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/process.py:315)
_launch (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/popen_fork.py:75)
__init__ (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/popen_fork.py:19)
_Popen (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/context.py:277)
_Popen (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/context.py:224)
start (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/process.py:121)
run_in_background (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/dht.py:141)
__init__ (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/dht.py:86)
main (/home/wxf/hm_prj/hm_master/hivemind/examples/albert/run_trainer.py:225)
<module> (/home/wxf/hm_prj/hm_master/hivemind/examples/albert/run_trainer.py:330)
```

# `self.get_stub(peer).rpc_ping(ping_request, timeout=self.wait_timeout)`

这个会 call 进 `class AuthRPCWrapper: __getattribute__`

```py
    def __getattribute__(self, name: str):
        if not name.startswith("rpc_"): # 没有进入
            return object.__getattribute__(self, name)

        method = getattr(self._stub, name)
```

逐行分析 code.

1.

`name`
```
'rpc_ping'
```

之所以是 'rpc_ping' 是因为调用者:

```py
response = await self.get_stub(peer).rpc_ping(ping_request, timeout=self.wait_timeout)
#                                   ^--------
```

所以 `.` 就是 `class AuthRPCWrapper def __getattribute__(self, name: str):`

## LOC

```
        method = getattr(self._stub, name)
```

`getattr`: https://www.programiz.com/python-programming/methods/built-in/getattr

等价于: `self._stub.name`

其中 `self._stub` 是
```
self._stub

<hivemind.p2p.servicer.DHTProtocolStub object at 0x7f5cc2742160>
special variables:
function variables:
_namespace: None
_p2p: <hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>
_peer: <libp2p.peer.id.ID (QmQAFagurooqVTo7VWksuKKsg7myvbLaJuhpuhHZCKN1sN)>
```

### Where is DHTProtocolStub?

It is not in the
```
hivemind/p2p/servicer.py
```

## 调用 `method = getattr(self._stub, name)` 的结果是 再次 call `method = getattr(self._stub, name)`

`method = getattr(self._stub, name)` 会再次调用这个类里面的 `def __getattribute__(self, name: str):` .

```py
    def __getattribute__(self, name: str):
        if not name.startswith("rpc_"):
            return object.__getattribute__(self, name)

        method = getattr(self._stub, name)

```

此时的 name 是 `'_stub'`.

```
name
'_stub'
```

因为 `method = getattr(self._stub, name)` 等价于 call 了 `self._stub.name`

而且 `getattr` ==> 会 call `__getattribute__`

因为 `if not name.startswith("rpc_"):` is `False`.

因此就调用了 `object.__getattribute__(self, name)`.

其中的 `name` 是 `'_stub'`.

返回到上一层 `method = getattr(self._stub, name)` 的 `method` 是

```py
method
<bound method ServicerBase._make_rpc_caller.<locals>.caller of <hivemind.p2p.servicer.DHTProtocolStub object at 0x7f5cc2742160>>
```

`_make_rpc_caller` is in `hivemind/p2p/servicer.py`, `def _make_rpc_caller(cls, handler: RPCHandler)`.

和 `hivemind/p2p/p2p_daemon.py` 相关.


## `@functools.wraps(method)`

it simply says, I want to pass method into the ` async def wrapped_rpc(request: AuthorizedRequestBase, *args, **kwargs):` as a parameter `method`.

and the `method` is

```
method
<bound method ServicerBase._make_rpc_caller.<locals>.caller of <hivemind.p2p.servicer.DHTProtocolStub object at 0x7f5cc2742160>>
```

# Call the wrapped method 

```
response = await self.get_stub(peer).rpc_ping(ping_request, timeout=self.wait_timeout)
```

```
response = await method(request, *args, **kwargs)
```

Call stack:

```
wrapped_rpc (/home/wxf/hm_prj/hm_master/hivemind/hivemind/utils/auth.py:205)
call_ping (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/protocol.py:106)
run (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/dht.py:134)
_bootstrap (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/process.py:315)
_launch (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/popen_fork.py:75)
__init__ (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/popen_fork.py:19)
_Popen (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/context.py:277)
_Popen (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/context.py:224)
start (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/process.py:121)
run_in_background (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/dht.py:141)
__init__ (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/dht.py:86)
main (/home/wxf/hm_prj/hm_master/hivemind/examples/albert/run_trainer.py:225)
<module> (/home/wxf/hm_prj/hm_master/hivemind/examples/albert/run_trainer.py:330)
```

跳转到  hivemind/p2p/servicer.py

```
    def _make_rpc_caller(cls, handler: RPCHandler):
```


再跳转到

```py
    async def call_protobuf_handler(
        self,
        peer_id: PeerID,
        name: str,
        input: Union[TInputProtobuf, TInputStream],
        output_protobuf_type: Type[Message],
    ) -> Awaitable[TOutputProtobuf]:

        if not isinstance(input, AsyncIterableABC):
            return await self._call_unary_protobuf_handler(peer_id, name, input, output_protobuf_type)

        responses = await self._iterate_protobuf_stream_handler(peer_id, name, input, output_protobuf_type)
        return await asingle(responses)
```

```
name
'DHTProtocol.rpc_ping'
```