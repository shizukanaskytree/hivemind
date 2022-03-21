

```py
cls._collect_rpc_handlers()
```

```py
    @classmethod
    def _collect_rpc_handlers(cls) -> None:
        if cls._rpc_handlers is not None: # 进入
            return
            #^^^^^
```

估计之前进来过.

```py
cls._rpc_handlers
[RPCHandler(method_na...tput=True), RPCHandler(method_na...tput=True), RPCHandler(method_na...tput=True)]

special variables:
function variables:

0: RPCHandler(method_name='rpc_aggregate_part', request_type=<class 'averaging_pb2.AveragingData'>, response_type=<class 'averaging_pb2.AveragingData'>, stream_input=True, stream_output=True)
1: RPCHandler(method_name='rpc_download_state', request_type=<class 'averaging_pb2.DownloadRequest'>, response_type=<class 'averaging_pb2.DownloadData'>, stream_input=False, stream_output=True)
2: RPCHandler(method_name='rpc_join_group', request_type=<class 'averaging_pb2.JoinRequest'>, response_type=<class 'averaging_pb2.MessageFromLeader'>, stream_input=False, stream_output=True)
len(): 3
```


```
cls._stub_type
<class 'hivemind.p2p.servicer.TrainingStateAveragerStub'>
```



























===