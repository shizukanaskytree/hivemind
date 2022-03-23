# dht in hivemind/moe/server/ps_server.py

DHT instance is used to `_declare_experts` (hivemind/moe/server/dht_handler.py) so that

```
    store_ok = await node.store_many(keys, values, expiration_time, subkeys=maybe_subkeys, num_workers=num_workers)
```