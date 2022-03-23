# from typing import Any, Callable, Dict, Sequence, Tuple, Union

# import torch
# from torch import nn

# from hivemind.moe.server.task_pool import TaskPool
# from hivemind.utils.logging import get_logger
# from hivemind.utils.nested import nested_compare, nested_flatten, nested_map, nested_pack
# from hivemind.utils.tensor_descr import DUMMY_BATCH_SIZE, BatchTensorDescriptor

# logger = get_logger(__name__)


# class PartitionedModelBackend:
#     """
#     push: remote trainer push its gradient to this PartitionedModelBackend
#     pull: remote trainer pull the partial model's parameter from this PartitionedModelBackend
#     """

#     def __init__(
#         self,
#         name: str,
#         expert: nn.Module,
#         optimizer: torch.optim.Optimizer,
#         *,
#         **kwargs,
#     ):
#         super().__init__()
#         self.expert, self.optimizer, self.name = expert, optimizer, name

#     def push(self, gradients):
#         """Remote trainer push gradients to this parameter server

#         gradients can be get by

#         ```
#         grads = []
#         for p in self.parameters():
#             grad = None if p.grad is None else p.grad.data.cpu().numpy()
#             grads.append(grad)
#         return grads
#         ```

#         """
#         ...

#     def pull(self, weight):
#         """

#         weight can be get by `return {k: v.cpu() for k, v in self.state_dict().items()}`
#         """
#         ...

