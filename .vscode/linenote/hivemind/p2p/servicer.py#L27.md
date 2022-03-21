# 道

`class DHTProtocol` is based on `class ServicerBase` (`hivemind/p2p/servicer.py`).


# Code

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

# Callstack

```
__init__ (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/servicer.py:28)
get_stub (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/servicer.py:128)
get_stub (/home/wxf/hm_prj/hm_master/hivemind/hivemind/dht/protocol.py:89)
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

实例化


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

`p2p`

```py
p2p

<hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>
special variables:
function variables:
BYTEORDER: 'big'
DHT_MODE_MAPPING: {'auto': {'dht': 1}, 'server': {'dhtServer': 1, 'bootstrapPeers': '/ip4/192.168.0.19/tc...uhHZCKN1sN', 'hostAddrs': '/ip4/0.0.0.0/tcp/0'}, 'client': {'dhtClient': 1}}
END_OF_STREAM:
ERROR_MARKER: b'\x01'
FORCE_REACHABILITY_MAPPING: {'public': {'forceReachabilityPublic': 1}, 'private': {'forceReachabilityPrivate': 1}}
HEADER_LEN: 8
MESSAGE_MARKER: b'\x00'
TInputProtobuf: ~TInputProtobuf
TInputStream: typing.AsyncIterator[~TInputProtobuf]
TOutputProtobuf: ~TOutputProtobuf
TOutputStream: typing.AsyncIterator[~TOutputProtobuf]
daemon_listen_maddr: <Multiaddr /unix/tmp/hivemind-p2pd-s3OvLuav-nI.sock>
is_alive: True
peer_id: <libp2p.peer.id.ID (QmSJhXXJpQYdDJGzjreSjgmw5FcoJzXvf741h7Hz3S7jGQ)>
_UNIX_SOCKET_PREFIX: '/unix/tmp/hivemind-'
_add_protobuf_stream_handler: <bound method P2P._add_protobuf_stream_handler of <hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>>
_add_protobuf_unary_handler: <bound method P2P._add_protobuf_unary_handler of <hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>>
_alive: True
_call_unary_protobuf_handler: <bound method P2P._call_unary_protobuf_handler of <hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>>
_child: <Process 202589>
_client: <hivemind.p2p.p2p_daemon_bindings.p2pclient.Client object at 0x7f5cc2756160>
_client_listen_maddr: <Multiaddr /unix/tmp/hivemind-p2pclient-s3OvLuav-nI.sock>
_convert_process_arg_type: <function P2P._convert_process_arg_type at 0x7f5baf987160>
_daemon_listen_maddr: <Multiaddr /unix/tmp/hivemind-p2pd-s3OvLuav-nI.sock>
_iterate_protobuf_stream_handler: <bound method P2P._iterate_protobuf_stream_handler of <hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>>
_listen_task: None
_log_p2pd_message: <function P2P._log_p2pd_message at 0x7f5baf987310>
_maddrs_to_str: <function P2P._maddrs_to_str at 0x7f5baf9871f0>
_make_process_args: <function P2P._make_process_args at 0x7f5baf9870d0>
_ping_daemon: <bound method P2P._ping_daemon of <hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>>
_read_outputs: <bound method P2P._read_outputs of <hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>>
_reader_task: <Task pending name='Task-2' coro=<P2P._read_outputs() running at /home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/p2p_daemon.py:581> wait_for=<Future pending cb=[<TaskWakeupMethWrapper object at 0x7f5cc2756730>()]>>
_start_listening: <bound method P2P._start_listening of <hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>>
_terminate: <bound method P2P._terminate of <hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>>
_visible_maddrs: (<Multiaddr /ip4/192....tcp/36064>, <Multiaddr /ip4/127....tcp/36064>)
```


`peer`

```
peer
<libp2p.peer.id.ID (QmQAFagurooqVTo7VWksuKKsg7myvbLaJuhpuhHZCKN1sN)>
```

`namespace`

```
namespace
None
```

# call stack 分析

[hivemind/dht/protocol.py](hivemind/dht/protocol.py)  <- ctrl click

```py
    def get_stub(self, peer: PeerID) -> AuthRPCWrapper:
        """get a stub that sends requests to a given peer"""
```

it only needs a `peer`.


