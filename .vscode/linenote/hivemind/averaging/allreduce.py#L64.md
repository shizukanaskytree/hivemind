# code

```py
class AllReduceRunner(ServicerBase):
    """
    An internal class that runs butterfly AllReduce in a predefined group of averagers.


    This class inherits hivemind.p2p.ServicerBase, so it can be used as an RPCServicer for testing purposes without
    creating a full DecentralizedAverager.

    :note: this class returns **differences** between averaged and local tensors in order to improve numerical stability


    :param p2p: a hivemind.p2p.P2P instance used for communication with other peers
    :param servicer_type: a hivemind.p2p.ServicerBase subclass whose RPC signatures are used
      when requesting other peers. Typically, it is DecentralizedAverager, its derivative,
      or AllReduceRunner itself (for testing purposes).
    :param prefix: namespace for servicer's RPCs (typically, equal to prefix for group keys)
    :param group_id: unique identifier of this specific all-reduce run
    :param tensors: local tensors that should be averaged with groupmates
    :param weight: scalar weight of this peer's tensors in the average (doesn't need to sum up to 1)
    :param peer_id: your peer_id, must be included in ordered_peer_ids
    :param ordered_peer_ids: group peer_ids ordered s.t. i-th peer_id is responsible for averaging i-th part
    :param peer_fractions: for each peer, a target fraction of vector elements that this peer should average
      (the actual number of values by peer will be nearly proportional, but there are no exact guarantees)
    :param modes: AveragingMode for each peer in ordered_peer_ids (normal, client-only or auxiliary)
    :param gathered: additional user-defined data collected from this group
    :param sender_timeout: during all_reduce, any sender that fails to send tensor chunk within this many seconds from
      previous chunk will be marked as failed and excluded from averaging. default: equal to next_chunk_timeout
    :param reducer_timeout: during all_reduce, any reducer that fails to send results chunk within this many seconds
      from previous chunk will be marked as failed and excluded from averaging. default: 2 x sender_timeout
    :param kwargs: additional parameters (e.g. part_size_bytes) will be passed to TensorPartContainer
    :note: Full-mode peers send and receive tensor parts concurrently, assuming a full-duplex TCP stream. In turn,
      non-averaging peers receive results only after they finish sending, which helps them avoid
      throughput issues in case of asymmetric high-latency connections (e.g. ACK compression).
    """

    def __init__(
        self,
        *,
        p2p: P2P,
        servicer_type: Type[ServicerBase],
        prefix: Optional[str],
        group_id: GroupID,
        tensors: Sequence[torch.Tensor],
        weight: Optional[float] = None,
        ordered_peer_ids: Sequence[PeerID],
        peer_fractions: Tuple[float, ...],
        modes: Optional[Sequence[AveragingMode]] = None,
        gathered: Optional[Dict[PeerID, Any]] = None,
        sender_timeout: Optional[float] = None,
        reducer_timeout: Optional[float] = None,
        **kwargs,
    ):
        self._p2p = p2p
        self.peer_id = p2p.peer_id
        assert self.peer_id in ordered_peer_ids, "peer_id is not a part of the group"
        if reducer_timeout is not None and (sender_timeout is None or reducer_timeout <= sender_timeout):
            raise ValueError(
                "If reducer_timeout is enabled, sender_timeout must be shorter than reducer_timeout. "
                "Otherwise, there is a chance that reducers will be banned while they await senders."
            )

        if not issubclass(servicer_type, ServicerBase):
            raise TypeError("`servicer_type` is expected to be a ServicerBase subclass")
        self._servicer_type = servicer_type
        self._prefix = prefix

        modes = modes or tuple(AveragingMode.CLIENT if frac == 0 else AveragingMode.NODE for frac in peer_fractions)
        assert len(modes) == len(ordered_peer_ids), "lists have inconsistent length"
        assert any(mode != AveragingMode.CLIENT for mode in modes), "cannot run allreduce without reducers"
        for mode, frac in zip(modes, peer_fractions):
            assert mode != AveragingMode.CLIENT or frac == 0, "client-mode peer should have zero all-reduce fraction"

        self.group_id, self.ordered_peer_ids = group_id, ordered_peer_ids
        self.modes, self.peer_fractions, self.gathered = modes, peer_fractions, gathered

        if weight is None:
            weight = float(modes[self.ordered_peer_ids.index(self.peer_id)] != AveragingMode.AUX)
        self.weight = weight

        self._future = asyncio.Future()

        self.sender_peer_ids = []
        for peer_id, mode in zip(self.ordered_peer_ids, modes):
            if mode != AveragingMode.AUX:
                self.sender_peer_ids.append(peer_id)

        self.sender_timeout, self.reducer_timeout = sender_timeout, reducer_timeout
        self.all_senders_started = asyncio.Event()
        self.banned_senders: Set[PeerID] = set()  # peers that did not send data by next_chunk_timeout
        self.banlock = asyncio.Lock()

        self.active_senders: Set[PeerID] = set()  # peers that began sending data via rpc_aggregate_part
        if self.peer_id in self.sender_peer_ids:
            self.active_senders.add(self.peer_id)
        if len(self.active_senders) == len(self.sender_peer_ids):
            self.all_senders_started.set()

        peer_id_index = self.ordered_peer_ids.index(self.peer_id)
        self.tensor_part_container = TensorPartContainer(tensors, peer_fractions, return_deltas=True, **kwargs)
        self.parts_for_local_averaging = self.tensor_part_container.get_raw_input_parts(peer_id_index)
        self.tensor_part_reducer = TensorPartReducer(
            tuple(part.shape for part in self.parts_for_local_averaging),
            len(self.sender_peer_ids),
        )
```

# Callstack

```
__init__ (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/allreduce.py:81)
_run_allreduce (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:522)
_run_internal (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:339)

---

run (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:870)
_bootstrap_inner (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:932)
_bootstrap (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:890)
```



# LOC

```py
        self._p2p = p2p
```

p2p type is P2P

```py
p2p
<hivemind.p2p.p2p_daemon.P2P object at 0x7f3932ec5e20>

special variables:
function variables:

BYTEORDER: 'big'
DHT_MODE_MAPPING: {'auto': {'dht': 1}, 'server': {'dhtServer': 1}, 'client': {'dhtClient': 1}}
END_OF_STREAM:
ERROR_MARKER: b'\x01'
FORCE_REACHABILITY_MAPPING: {'public': {'forceReachabilityPublic': 1}, 'private': {'forceReachabilityPrivate': 1}}
HEADER_LEN: 8
MESSAGE_MARKER: b'\x00'
TInputProtobuf: ~TInputProtobuf
TInputStream: typing.AsyncIterator[~TInputProtobuf]
TOutputProtobuf: ~TOutputProtobuf
TOutputStream: typing.AsyncIterator[~TOutputProtobuf]
daemon_listen_maddr: <Multiaddr /unix/tmp/hivemind-p2pd-M2SwWLdDLs4.sock>
is_alive: True
peer_id: <libp2p.peer.id.ID (QmaK5PbuSStGb1DrdGishTM84s3FYvXpDzddkLib9edumT)>
_UNIX_SOCKET_PREFIX: '/unix/tmp/hivemind-'
_add_protobuf_stream_handler: <bound method P2P._add_protobuf_stream_handler of <hivemind.p2p.p2p_daemon.P2P object at 0x7f3932ec5e20>>
_add_protobuf_unary_handler: <bound method P2P._add_protobuf_unary_handler of <hivemind.p2p.p2p_daemon.P2P object at 0x7f3932ec5e20>>
_alive: True
_call_unary_protobuf_handler: <bound method P2P._call_unary_protobuf_handler of <hivemind.p2p.p2p_daemon.P2P object at 0x7f3932ec5e20>>
_child: None
_client: <hivemind.p2p.p2p_daemon_bindings.p2pclient.Client object at 0x7f3932ec5fd0>
_client_listen_maddr: <Multiaddr /unix/tmp/hivemind-p2pclient-MncdL0iiBl0.sock>
_convert_process_arg_type: <function P2P._convert_process_arg_type at 0x7f3892302040>
_daemon_listen_maddr: <Multiaddr /unix/tmp/hivemind-p2pd-M2SwWLdDLs4.sock>
_iterate_protobuf_stream_handler: <bound method P2P._iterate_protobuf_stream_handler of <hivemind.p2p.p2p_daemon.P2P object at 0x7f3932ec5e20>>
_listen_task: <Task pending name='Task-24' coro=<P2P._start_listening.<locals>.listen() running at /home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/p2p_daemon.py:514> wait_for=<Future pending cb=[<TaskWakeupMethWrapper object at 0x7f393dc19f10>()]>>
_log_p2pd_message: <function P2P._log_p2pd_message at 0x7f38923021f0>
_maddrs_to_str: <function P2P._maddrs_to_str at 0x7f38923020d0>
_make_process_args: <function P2P._make_process_args at 0x7f38922fef70>
_ping_daemon: <bound method P2P._ping_daemon of <hivemind.p2p.p2p_daemon.P2P object at 0x7f3932ec5e20>>
_read_outputs: <bound method P2P._read_outputs of <hivemind.p2p.p2p_daemon.P2P object at 0x7f3932ec5e20>>
_reader_task: None
_start_listening: <bound method P2P._start_listening of <hivemind.p2p.p2p_daemon.P2P object at 0x7f3932ec5e20>>
_terminate: <bound method P2P._terminate of <hivemind.p2p.p2p_daemon.P2P object at 0x7f3932ec5e20>>
_visible_maddrs: (<Multiaddr /ip4/192....tcp/35313>, <Multiaddr /ip4/127....tcp/35313>)
```


`class P2P:` is in `hivemind/p2p/p2p_daemon.py`.

```
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
```

too much.


```py

```

```py

```

```py

```


```py

```

```py

```

```py

```

```py

```


```py

```

```py

```

```py

```

```py

```


```py

```

```py

```

```py

```

```py

```


```py

```

```py

```

```py

```

```py

```



```py

```

```py

```

```py

```

```py

```



```py

```

```py

```

```py

```

```py

```



```py

```

```py

```

```py

```

```py

```