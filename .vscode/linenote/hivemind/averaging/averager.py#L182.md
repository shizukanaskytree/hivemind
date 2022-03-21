`self._averaged_tensors` 的一生



```
    averager1 = GradientAverager(
        model1.parameters(), dht=dht1, prefix="test", target_group_size=2, reuse_grad_buffers=False, start=True
        #------------------
    )
```


```
    def __init__(
        self,
        parameters: Iterable[torch.nn.Parameter],
        #---------------------------------------

        *,
        dht: hivemind.DHT,
        prefix: str,
        reuse_grad_buffers: bool = False,
        accumulate_grads_on: Optional[torch.device] = None,
        client_mode: bool = None,
        warn: bool = True,
        **kwargs,
    ):
```


```py
__init__ (/home/wxf/hm_prj/hm_master/hivemind/hivemind/averaging/averager.py:182)

__init__ (/home/wxf/hm_prj/hm_master/hivemind/hivemind/optim/grad_averager.py:101)
---------

test_grad_averager (/home/wxf/hm_prj/hm_master/hivemind/tests_wxf/test_grad_average.py:28)
<module> (/home/wxf/hm_prj/hm_master/hivemind/tests_wxf/test_grad_average.py:81)
```

```py
class GradientAverager(DecentralizedAverager):

        with torch.no_grad():
            averaged_grads = tuple(
                grad.detach().cpu().clone().share_memory_() for grad in self._grads_from_parameters()
            )
        super().__init__(averaged_tensors=averaged_grads, dht=dht, prefix=prefix, client_mode=client_mode, **kwargs)
```




