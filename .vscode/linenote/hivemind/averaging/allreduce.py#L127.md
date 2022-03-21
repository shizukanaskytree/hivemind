
```
self.tensor_part_container = TensorPartContainer(tensors, peer_fractions, return_deltas=True, **kwargs)
```

这个变量是什么?

```py
class TensorPartContainer:
    """
    Auxiliary data structure for averaging, responsible for splitting tensors into parts and reassembling them.
    The class is designed to avoid excessive memory allocation and run all heavy computation in background

    :param tensors: local tensors to be split and aggregated
    :param peer_fractions: for each peer, a target fraction of vector elements that this peer should average
    :param compression: optionally compress tensors with this compression algorithm before sending them to peers
    :param part_size_bytes: greedily split tensors into parts of up to this many bytes (after compression)
    :param tensor_infos: CompressionInfo for each respective tensor; this determines how the tensor will be comressed
    :param return_deltas: if True, output tensors are differences (aggregated tensor - local tensor)
    :param prefetch: when compressing, pre-compute this many compressed tensors in background
    """

```