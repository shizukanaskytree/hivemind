```
        return await self.control.stream_open(peer_id=peer_id, protocols=protocols)
```

call

```py
    async def stream_open(
        self, peer_id: PeerID, protocols: Sequence[str]
    ) -> Tuple[StreamInfo, asyncio.StreamReader, asyncio.StreamWriter]:
        reader, writer = await self.daemon_connector.open_connection()

        stream_open_req = p2pd_pb.StreamOpenRequest(peer=peer_id.to_bytes(), proto=list(protocols))
        req = p2pd_pb.Request(type=p2pd_pb.Request.STREAM_OPEN, streamOpen=stream_open_req)
        await write_pbmsg(writer, req)

        resp = p2pd_pb.Response()  # type: ignore
        await read_pbmsg_safe(reader, resp)
        raise_if_failed(resp)

        pb_stream_info = resp.streamInfo
        stream_info = StreamInfo.from_protobuf(pb_stream_info)

        return stream_info, reader, writer
```



```py
    async def open_connection(self) -> (asyncio.StreamReader, asyncio.StreamWriter):
        if self.proto_code == protocols.P_UNIX:
            control_path = self.control_maddr.value_for_protocol(protocols.P_UNIX)
            return await asyncio.open_unix_connection(control_path)
        elif self.proto_code == protocols.P_IP4:
            host = self.control_maddr.value_for_protocol(protocols.P_IP4)
            port = int(self.control_maddr.value_for_protocol(protocols.P_TCP))
            return await asyncio.open_connection(host, port)
        else:
            raise ValueError(f"Protocol not supported: {protocols.protocol_with_code(self.proto_code)}")

```


```
protocols.P_UNIX
400
```

```
control_path
'/tmp/hivemind-p2pd-crLwUqv0_9s.sock'
```


Unix Sockets

```
coroutine asyncio.open_unix_connection(path=None, *, limit=None, ssl=None, sock=None, server_hostname=None, ssl_handshake_timeout=None)
```

Establish a Unix socket connection and return a pair of `(reader, writer)`.

Similar to `open_connection()` but operates on Unix sockets.

See also the documentation of `loop.create_unix_connection()`.

Availability: Unix.

Changed in version 3.7: Added the ssl_handshake_timeout parameter. The path parameter can now be a path-like object

Changed in version 3.10: Removed the loop parameter.


# Call stack

```
stream_open (/home/wxf/hm_prj/hm_master/hivemind/hivemind/p2p/p2p_daemon_bindings/p2pclient.py:106)
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

