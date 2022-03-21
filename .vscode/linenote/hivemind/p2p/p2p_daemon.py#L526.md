`return await self._client.stream_open(peer_id, (handler_name,))`

Call

```
    async def stream_open(
        self, peer_id: PeerID, protocols: Sequence[str]
    ) -> Tuple[StreamInfo, asyncio.StreamReader, asyncio.StreamWriter]:
        """
        Open a stream to call other peer (with peer_id) handler for specified protocols
        :peer_id: other peer id
        :protocols: list of protocols for other peer handling
        :return: Returns tuple of stream info (info about connection to second peer) and reader/writer
        """
        return await self.control.stream_open(peer_id=peer_id, protocols=protocols)
```


# call stack

支线 thread-14

```
call_binary_stream_handler (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/p2p_daemon.py:526)
_iterate_protobuf_stream_handler (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/p2p_daemon.py:387)
iterate_protobuf_handler (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/p2p_daemon.py:509)
caller (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/servicer.py:102)
_load_state_from_peers (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:706)
_run_internal (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:339)
run (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:870)
_bootstrap_inner (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:932)
_bootstrap (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:890)
```