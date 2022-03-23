"""
This file is used to invoke the ps server

"""
from functools import partial
from pathlib import Path

import configargparse
import torch

from hivemind.utils.limits import increase_file_limit
from hivemind.moe.server import ParameterServer

def main():
    parser = configargparse.ArgParser()
    parser.add_argument('--num_handlers', type=int, default=None, required=False,
                        help='server will use this many processes to handle incoming requests')
    parser.add_argument('--optimizer', type=str, default='adam', required=False, help='adam, sgd or none')
    parser.add_argument('--initial_peers', type=str, nargs='*', required=False, default=[],
                        help='multiaddrs of one or more active DHT peers (if you want to join an existing DHT)')
    parser.add_argument('--increase_file_limit', action='store_true',
                        help='On *nix, this will increase the max number of processes '
                             'a server can spawn before hitting "Too many open files"; Use at your own risk.')
    parser.add_argument('--checkpoint_dir', type=Path, required=False, help='Directory to store expert checkpoints')
    parser.add_argument('--stats_report_interval', type=int, required=False,
                        help='Interval between two reports of batch processing performance statistics')

    # fmt:on
    args = vars(parser.parse_args())
    args.pop("config", None)

    optimizer = args.pop("optimizer")
    if optimizer == "adam":
        optim_cls = torch.optim.Adam
    elif optimizer == "sgd":
        optim_cls = partial(torch.optim.SGD, lr=0.01)
    elif optimizer == "none":
        optim_cls = None
    else:
        raise ValueError("optim_cls must be adam, sgd or none")

    if args.pop("increase_file_limit"):
        increase_file_limit()

    ps_server = ParameterServer.create(**args, optim_cls=optim_cls, start=True)

    try:
        ps_server.join()
    except KeyboardInterrupt:
        ps_server.info("Caught KeyboardInterrupt, shutting down")
    finally:
        ps_server.shutdown()

if __name__ == "__main__":
    main()
