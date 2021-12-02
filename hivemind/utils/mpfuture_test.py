from mpfuture import SharedBytes, MPFuture 

import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
debugpy.breakpoint()

sb = SharedBytes

# 初始化
# ---
# ./dht/dht.py:75:        self._ready = MPFuture()
# ./dht/dht.py:171:        future = MPFuture()
# ./dht/dht.py:204:        future = MPFuture()
# ---
# MPFuture[ReturnType], 用中括号表示类型
# ---
# MPFuture[RemoteExpert]

mpf = MPFuture()
print("xxx")


# 
# https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.result
