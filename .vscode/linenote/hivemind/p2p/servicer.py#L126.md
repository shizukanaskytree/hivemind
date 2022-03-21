# Code


```py
    @classmethod
    def get_stub(cls, p2p: P2P, peer: PeerID, *, namespace: Optional[str] = None) -> StubBase:
        cls._collect_rpc_handlers()
        return cls._stub_type(p2p, peer, namespace)
```

# callstack

```
get_stub (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/servicer.py:127)
get_stub (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/protocol.py:89)
call_find (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/protocol.py:287)
_call_find_with_blacklist (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/node.py:696)
get_neighbors (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/node.py:637)
run (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/dht.py:134)

------
_bootstrap (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/process.py:315)
_launch (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/popen_fork.py:75)
__init__ (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/popen_fork.py:19)
_Popen (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/context.py:277)
_Popen (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/context.py:224)
start (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/multiprocessing/process.py:121)
------

run_in_background (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/dht.py:141)
__init__ (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/dht.py:86)
main (/home/wxf/hm_prj/hm_master/hivemind/examples/albert/run_trainer.py:224)
<module> (/home/wxf/hm_prj/hm_master/hivemind/examples/albert/run_trainer.py:329)
```


# 理解 `cls._stub_type(p2p, peer, namespace)`

```py
        return cls._stub_type(p2p, peer, namespace)
```

本质上是 call the `__init__` of the `class StubBase`.

传入的三个参数是 `class StubBase` 内的 `p2p: P2P, peer: PeerID, namespace: Optional[str]`

```py
class StubBase:
    """
    Base class for P2P RPC stubs. The interface mimicks gRPC stubs.

    Servicer derives stub classes for particular services (e.g. DHT, averager, etc.) from StubBase,
    adding the necessary rpc_* methods. Calls to these methods are translated to calls to the remote peer.
    """

    def __init__(self, p2p: P2P, peer: PeerID, namespace: Optional[str]):
        self._p2p = p2p
        self._peer = peer
        self._namespace = namespace
```

此外, 再赘述一句是: `cls._stub_type` 是

```py
class ServicerBase:
    _stub_type: Optional[Type[StubBase]] = None
```


# called by

[ref 1](.vscode/linenote/hivemind/averaging/averager.py#L683.md)
