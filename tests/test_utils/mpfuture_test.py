"""
Test file list:

variable logger
variable ResultType
constant PID
constant UID
variable State
variable PipeEnd
constant ALL_STATES
constant TERMINAL_STATES

class InvalidStateError

class SharedBytes
	variable _lock
	variable _pid
	variable _buffer
	variable _index

	method next ✅✅
		variable buffer_size

class UpdateType
	constant RESULT
	constant EXCEPTION
	constant CANCEL
 
class MPFuture
	variable _initialization_lock
	variable _update_lock
	variable _global_sender_pipe
	variable _pipe_waiter_thread
	variable _active_futures
	variable _active_pid
 
	method __init__ ✅✅
		variable use_lock
  
	method _state ✅
		variable new_state
  
	method _set_event_threadsafe ✅
		variable running_loop
		function _event_setter
  
	method _initialize_mpfuture_backend ✅✅
		variable pid
		variable receiver_pipe
  
	method reset_backend ✅
 
	method _process_updates_in_background ✅✅
		variable receiver_pipe
		variable pid
		variable uid
		variable update_type
		variable payload
		variable future
		variable future_ref
		variable e
  
	method _send_update ✅
		variable update_type
		variable payload
		variable e
  
	method set_result ✅
		variable result
  
	method set_exception ✅
		variable exception
  
	method cancel ✅
 
	method set_running_or_notify_cancel
 
	method result ✅
		variable timeout
  
	method exception ✅
		variable timeout
  
	method done
 
	method running
 
	method cancelled
 
	method add_done_callback
		variable callback
  
	method __await__
 
	method __del__
 
	method __getstate__
 
	method __setstate__
		variable state
  
	variable _origin_pid
	variable _uid
	variable _shared_state_code
	variable _state_cache
	variable _result
	variable _exception
	variable _use_lock
	variable _sender_pipe
	variable _loop
	variable _aio_event
	variable _waiters
	variable _done_callbacks
	variable _condition
"""

import unittest
from hivemind.utils.mpfuture import SharedBytes, MPFuture 

import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
debugpy.breakpoint()

class TestSharedBytesMethods(unittest.TestCase):  
    def test_sharedbytes(self):
        sb = SharedBytes

class TestMPFutureMethods(unittest.TestCase):  
    def test_mpfuture_part1(self):
        # https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.result
        
				# 这个测试完成了接口.
        mpf = MPFuture()
        print(mpf._state)
        cnt = 0
        mpf.set_result(cnt)
        self.assertEqual(mpf.result(), 0)
        mpf.reset_backend()
        mpf.cancel()

    def test_part2(self):
        # 初始化
        # ---
        # ./dht/dht.py:75:         self._ready = MPFuture()
        # ./dht/dht.py:171:        future = MPFuture()
        # ./dht/dht.py:204:        future = MPFuture()
        # ---
        # MPFuture[ReturnType], 用中括号表示类型
        # ---
        # MPFuture[RemoteExpert]

        mpf = MPFuture()
        # 也就是其他 process 可以做.
        mpf.set_result(123)
        # mpf.set_result("abc") # 不能执行两次 set_result.

        """
        ERROR:

        Traceback (most recent call last):
        File "mpfuture_test.py", line 24, in <module>
            mpf.set_result("abc")
        File "/home/wxf/netmind_prj/study_hivemind/hivemind/hivemind/utils/mpfuture.py", line 211, in set_result
            super().set_result(result)
        File "/home/wxf/anaconda3/envs/hm/lib/python3.8/concurrent/futures/_base.py", line 532, in set_result
            raise InvalidStateError('{}: {!r}'.format(self._state, self))
        concurrent.futures._base.InvalidStateError: FINISHED: <MPFuture at 0x7fb1fa586910 state=finished returned int>
        """        

    def test_part3(self):
        mpf = MPFuture()
        try:
            raise Exception
        except Exception as e:
            print('except...')
            mpf.set_exception(e)
            return        


if __name__ == '__main__':
    unittest.main()