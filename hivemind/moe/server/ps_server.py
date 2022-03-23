# import threading
# from typing import Awaitable, Callable, Iterable, List, Optional, Sequence, TypeVar, Union

# from hivemind.dht import DHT
# from multiaddr import Multiaddr
# from src.utils import get_logger
# from hivemind.moe.server.layers import (
#     add_custom_models_from_file,
#     name_to_block,
#     name_to_input,
#     register_expert_class,
#     schedule_name_to_scheduler,
# )

# logger = get_logger(__name__)

# class ParameterServer(threading.Thread):
#     """The parameter server will hold a copy of the model.

#     During training, it will:
#     1. Receive gradients and apply them to its model.
#     2. Send the updated model back to the workers.

#     """

#     def __init__(self, ):
#         # 1. define the model
#         # 2. define the optimizer to update the model after receiving the gradients
#         # 3. dht to connect with each other

#         # 1.
#         # use dict to store partial models
#         ...

#     @classmethod
#     def create(
#         cls,
#         dht: Optional[DHT],
#         initial_peers: Optional[Sequence[Union[Multiaddr, str]]] = None


#     ) -> ParameterServer:
#         """
#         :param initial_peers: multiaddrs of one or more active DHT peers (if you want to join an existing DHT)
#         """

#         dht = DHT(initial_peers=initial_peers, start=True)
#         visible_maddrs_str = [str(a) for a in dht.get_visible_maddrs()]
#         logger.info(f"Running DHT node on {visible_maddrs_str}, initial peers = {initial_peers}")

#         # initialize partial models as model_experts from hivemind/moe/server/layers/albert.py
#         # expert_cls: lm_head lm_body lm_tail
#         # 怎么传 weights? 这个不会. 


#     def apply_gradients(self, *gradients):
#         ...

#     def get_weights(self):
#         ...
