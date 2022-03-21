# code

```py
async def aiter_with_timeout(iterable: AsyncIterable[T], timeout: Optional[float]) -> AsyncIterator[T]:
    """Iterate over an async iterable, raise TimeoutError if another portion of data does not arrive within timeout"""
    # based on https://stackoverflow.com/a/50245879
    iterator = iterable.__aiter__()
    while True:
        try:
            yield await asyncio.wait_for(iterator.__anext__(), timeout=timeout)
        except StopAsyncIteration:
            break

```

# call stack

```
aiter_with_timeout (/home/wxf/hm_prj/hm_master/hivemind/hivemind/utils/asyncio.py:154)
_load_state_from_peers (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:709)
_run_internal (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:339)
run (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:870)
_bootstrap_inner (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:932)
_bootstrap (/home/wxf/anaconda3/envs/hm_master/lib/python3.8/threading.py:890)
```

# iterator

```
iterator
<async_generator object P2P._iterate_protobuf_stream_handler.<locals>._read_from_stream at 0x7f0b3f56cca0>
```