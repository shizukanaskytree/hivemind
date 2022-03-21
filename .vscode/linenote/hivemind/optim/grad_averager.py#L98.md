这不是还没有平均吗
待平均, 需要被平均的 gradients

```py
with torch.no_grad():
    averaged_grads = tuple(
        grad.detach().cpu().clone().share_memory_() for grad in self._grads_from_parameters()
    )
```
