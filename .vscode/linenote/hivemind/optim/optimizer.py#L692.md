If it fails, it will continue trying since it is in a while loop.

```py
        with self.tracker.pause_updates():
            while True:
                try:
                    self.state_averager.load_state_from_peers(timeout=self.load_state_timeout, **kwargs)
                    break
                except KeyboardInterrupt:
                    raise
                except BaseException as e:
                    logger.exception(f"Failed to load state from peers: {e}, retrying ...")
                    continue
```



