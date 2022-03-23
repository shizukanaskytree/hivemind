```py

worker_service = WorkerService(...)


with worker_service.get_tensors() as tensors:
    # run some code, modify tensors if necessary
    tensors[0] += 1

# do not use tensors after the lock is released
metadata = worker_service.step(gather=dict(my_batch_size=32))

# run averaging once (in-place), gather metadata from groupmates
with worker_service.get_tensors() as tensors_after_averaging:

    pass # use the averaged tensors

```