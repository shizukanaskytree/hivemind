from __future__ import annotations

import asyncio
import concurrent.futures._base as base
# concurrent.futures
# https://docs.python.org/3/library/concurrent.futures.html

import multiprocessing as mp
import multiprocessing.connection
import os
import threading
import uuid
from contextlib import nullcontext
from enum import Enum, auto
from typing import Any, Callable, Dict, Generic, Optional, Type, TypeVar
from weakref import ref

import torch  # used for py3.7-compatible shared memory

from hivemind.utils.logging import get_logger

logger = get_logger(__name__)

"""
evaluation comment:
这个还需要一直看, 一直看, 感觉不懂.


What is the design?
===================
可能是带有
异步执行模块
- set result 
- get result
- notify it is done
- set exception async..ly

设计的思路:
=========
1. A process-wide object that allocates large chunks of shared memory 
   and partitions it into individual bytes.

2. if True, operations with MPFuture use a global lock to prevent 
   concurrent writes to the same pipe;

用在了哪里?
=========
./dht/dht.py:15: from hivemind.utils import MPFuture, get_logger, switch_to_uvloop
- self._ready = MPFuture()
- self._ready.set_exception(e)
- self._ready.set_result(None)
- self._ready.result(timeout=timeout)
- if not self._ready.done():

---

./averaging/averager.py:206:      self._ready = MPFuture()
- self._ready = MPFuture()
- self._ready.set_exception(e)
- self._ready.set_result(None)
- self._ready.result(timeout=timeout)

---

./averaging/control.py:46:        self._trigger: Optional[MPFuture] = None
- done()
- cancel()
- set_result()

---

./moe/server/task_pool.py:103:        task = Task(MPFuture(), args)
- task = Task(MPFuture(), args)
- task.future.set_exception(exc)


---

./moe/client/beam_search.py:233:    ) -> Union[List[RemoteExpert], MPFuture[RemoteExpert]]:
"""

# flavour types
ResultType = TypeVar("ResultType")

PID, UID, State, PipeEnd = int, int, str, mp.connection.Connection

ALL_STATES = base.PENDING, base.RUNNING, base.FINISHED, base.CANCELLED, base.CANCELLED_AND_NOTIFIED
# 这个是一个状态机吗?

TERMINAL_STATES = {base.FINISHED, base.CANCELLED, base.CANCELLED_AND_NOTIFIED}

try:
    from concurrent.futures import InvalidStateError
except ImportError:
    # Python 3.7 doesn't raise concurrent.futures.InvalidStateError for repeating set_result/set_exception calls and
    # doesn't even define this error. In this module, we simulate the Python 3.8+ behavior,
    # defining and raising this error if necessary.
    class InvalidStateError(Exception):
        """Raised when attempting to change state of a future in a terminal state (e.g. finished)"""


class SharedBytes:
    """
    A process-wide object that allocates large chunks of shared memory and 
    partitions it into individual bytes.

    Note: this process is only responsible for bulk allocation, it does not manage/free unused bytes.
    The chunks are deallocated by the garbage collector,
    when it detects that all processes no longer use any bytes from this chunk.
    """

    _lock = mp.Lock()
    _pid: Optional[PID] = None
    # 初始的 pid 就是 None 
    # PID is int
    # Optional: https://stackoverflow.com/questions/51710037/how-should-i-use-the-optional-type-hint
    
    _buffer: Optional[torch.Tensor] = None
    # ...
    
    _index: int = 0
    # ?
    
    @classmethod
    def next(cls) -> torch.Tensor:
        """Create another shared byte value, represented as a scalar uint8 tensor"""
        with cls._lock:
            if cls._pid != os.getpid() or cls._buffer is None or cls._index >= len(cls._buffer):
                # 1.
                # 想象成电路逻辑图, 超级爽. 
                
                # 2.
                # len(cls._buffer)
                # 16
                
                # 3. 
                # 初始情况, 
                # cls._pid 是 None
                # cls._buffer 是 None
                
                buffer_size = int(os.environ.get("HIVEMIND_SHM_BUFFER_SIZE", 16))
                # print(os.getenv('KEY_THAT_MIGHT_EXIST', default_value))

                cls._pid = os.getpid()
                cls._buffer = torch.empty([buffer_size], dtype=torch.uint8).share_memory_()
                # share_memory_
                # https://pytorch.org/docs/stable/generated/torch.Tensor.share_memory_.html
                # 
                # tensor.share_memory_() will move the tensor data to shared memory on the host so that it can be shared between multiple processes. 
                # The Wikipedia article 89 explains shared memory maybe a bit easier to understand.
                # It’s basically a memory pool, which can be used by multiple processes to exchange information and data.
                # https://discuss.pytorch.org/t/what-is-the-shared-memory/112212

                cls._index = 0

            cls._index += 1
            return cls._buffer[cls._index - 1]
            # 怎么弄, cls._index 都是 0
            # 
    """
    记一次测试.

    self._origin_pid
    2145657
    self._uid
    51395721929927224078887597689317331691


    cls._pid
    None


    buffer_size
    16


    cls._pid
    2145657


    cls._buffer
    tensor([123,  86, 244,  39, 235, 122, 146,  74,  48,  52, 227, 206, 167, 127,
            0,   0], dtype=torch.uint8)


    cls._buffer.size()
    torch.Size([16])


    cls._index
    1


    cls._buffer[cls._index - 1]
    tensor(123, dtype=torch.uint8)
    """



class UpdateType(Enum):
    RESULT = auto()
    EXCEPTION = auto()
    CANCEL = auto()
# Enum
# An enumeration is a set of symbolic names (members) bound to unique, constant values.


class MPFuture(base.Future, Generic[ResultType]):
    # 为什么要继承自 Generic[ResultType] 呢? 看上面的用例
    # ResultType is the value type of set_result() and result()

    # Future 功能应该就是 MPFuture 的功能. 
    # concurrent.futures
    # https://docs.python.org/3/library/concurrent.futures.html 
    # The concurrent.futures module provides a high-level interface for asynchronously
    # executing callables.

    # The Future class encapsulates the asynchronous execution of a callable. 
    # Future instances are created by Executor.submit().
    # https://docs.python.org/3/library/concurrent.futures.html#future-objects
    
    # 使用的场景应该是和 base.Future 一样的吧?
    # 用例: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.result
    # 好像不太一样.
    
    """
    功能:
    A version of concurrent.futures.Future / asyncio.Future that can be fulfilled from a separate process.
    
    **Any process** can access future status and set the result / exception and check for state.
    However, only the original process (i.e. the process that created the future) can await the result or exception.

    study syntax:
    :param VAR:
    :note:

    :param use_lock: if True, operations with MPFuture use a global lock to prevent concurrent writes to the same pipe;
      If set to False, writing to this future ignores global lock, slightly 稍微 improving performance, but making user
      responsible for avoiding concurrent set_result / set_exception calls to futures with the same process of origin.
    
    - takeaway
      - lock
      - concurrent writes
      - pipe

    :note: This is an internal primitive that is not guaranteed to work outside of hivemind 
            applications.
            
     More specifically, there are two known limitations:
       - MPFuture works between processes created through inheritance (e.g. fork), *not* for independent processes
       - MPFuture is deterministic if only one process can call set_result/set_exception/set_running_or_notify_cancel
         and only the origin process can call result/exception/cancel.
    
    - takeaway
      - set_result
      - set_exception
      - set_running_or_notify_cancel
    
    """

    _initialization_lock = mp.Lock()  
    # global lock that prevents simultaneous initialization of two processes
    # import multiprocessing as mp
    
    # 这个锁用在 __init__ 函数里面.
    
    _update_lock = mp.Lock()  
    # global lock that prevents simultaneous writing to the same pipe
    
    _global_sender_pipe: Optional[PipeEnd] = None  
    # a pipe that is used to send results/exceptions to this process
    
    _pipe_waiter_thread: Optional[threading.Thread] = None  
    # process-specific thread that receives results/exceptions
    
    _active_futures: Optional[Dict[UID, "ref[MPFuture]"]] = None  
    # non-done futures originated from this process
    
    _active_pid: Optional[PID] = None  
    # pid of currently active process; used to handle forks natively

    def __init__(self, *, use_lock: bool = True):
        # 如果使用 lock, use_lock is True.
        # 上面写了.
        
        # If all you want is a unique ID, you should probably call uuid1() or uuid4()
        # https://docs.python.org/3/library/uuid.html
        self._origin_pid, self._uid = os.getpid(), uuid.uuid4().int
        # The process who creates this Future is the original pid with a unique id.
        
        self._shared_state_code = SharedBytes.next()
        
        self._state_cache: Dict[State, State] = {}
        # mapping from global to cached local future used that makes updates immediately
        # available on setter side; dictionary-based cache works because future can visit 
        # any state at most once
        # State IS str

        base.Future.__init__(self)  
        # parent init is deferred because it uses self._shared_state_code
        # ========================
        # class Future(object):
        #     """Represents the result of an asynchronous computation."""
        #
        #     def __init__(self):
        #         """Initializes the future. Should not be called by clients."""
        #         self._condition = threading.Condition()
        #         self._state = PENDING
        #         self._result = None
        #         self._exception = None
        #         self._waiters = []
        #         self._done_callbacks = []        
        # 重要:
        # from:
        # /home/wxf/anaconda3/envs/hm/lib/python3.8/concurrent/futures/_base.py
        
        # self._state = PENDING 会调用 本文件中的这个函数: 
        #
        #    @_state.setter
        #     def _state(self, new_state: State):
        #         self._shared_state_code[...] = ALL_STATES.index(new_state)
        #         if self._state in TERMINAL_STATES and self._loop is not None and not self._aio_event.is_set():
        #             self._set_event_threadsafe()
        
        # 分析一下 @_state.setter, _state
        # 
        # ALL_STATES
        # ('PENDING', 'RUNNING', 'FINISHED', 'CANCELLED', 'CANCELLED_AND_NOTIFIED')
        
        # new_state
        # 'PENDING'

        # ALL_STATES.index(new_state)
        # 0
                
        # self._shared_state_code
        # tensor(144, dtype=torch.uint8)
        
        # self._shared_state_code[...]
        # tensor(144, dtype=torch.uint8)

        # self._state 在 setter 函数里面是有调用
        # @property
        # def _state(self) -> State:
        #     shared_state = ALL_STATES[self._shared_state_code.item()]
        #     return self._state_cache.get(shared_state, shared_state)

        # self._shared_state_code.item()
        # https://pytorch.org/docs/stable/generated/torch.Tensor.item.html
        # Returns the value of this tensor as a standard Python number. 
        # This only works for tensors with one element. For other cases, see tolist().

        # shared_state
        # 'PENDING'
        # ALL_STATES
        # ('PENDING', 'RUNNING', 'FINISHED', 'CANCELLED', 'CANCELLED_AND_NOTIFIED')
        
        # self._state_cache: Dict[State, State] = {}        
        
        self._state, self._result, self._exception = base.PENDING, None, None
        
        self._use_lock = use_lock

        """
        测试: 
        self._origin_pid
        2145657
        MPFuture._active_pid
        None
        """
        if self._origin_pid != MPFuture._active_pid: # 一次检测
            # MPFuture._active_pid is None
            # 
            with MPFuture._initialization_lock:
                # lock it!
                
                if self._origin_pid != MPFuture._active_pid: # 两次检测
                    # note: the second if is intentional, 
                    # see https://en.wikipedia.org/wiki/Double-checked_locking
                    # In software engineering, double-checked locking (also known 
                    # as "double-checked locking optimization"[1]) is a software 
                    # design pattern used to reduce the overhead of acquiring a 
                    # lock by testing the locking criterion (the "lock hint") 
                    # before acquiring the lock. Locking occurs only if the locking 
                    # criterion check indicates that locking is required.
                    # 
                    # https://www.cs.cornell.edu/courses/cs6120/2019fa/blog/double-checked-locking/
                    # 这个可以告诉你在干什么. 
                    self._initialize_mpfuture_backend()
        
        assert self._uid not in MPFuture._active_futures
        
        MPFuture._active_futures[self._uid] = ref(self)
        
        self._sender_pipe = MPFuture._global_sender_pipe

        try:
            self._loop = asyncio.get_event_loop()
            # The event loop is the core of every asyncio application. 
            # Event loops run asynchronous tasks and callbacks, perform 
            # network IO operations, and run subprocesses.
            # https://docs.python.org/3/library/asyncio-eventloop.html
            # Get the current event loop.

            self._aio_event = asyncio.Event()
            # Create an Event object.
            # An asyncio event can be used to notify multiple asyncio tasks that some event has happened.
            # An Event object manages an internal flag that can be set to true with the set() method and reset to false with the clear() method. The wait() method blocks until the flag is set to true. The flag is set to false initially.
            # https://docs.python.org/3/library/asyncio-sync.html#event            
            
        except RuntimeError:
            self._loop, self._aio_event = None, None

    @property
    def _state(self) -> State:
        # State IS str, 什么用途?        
        shared_state = ALL_STATES[self._shared_state_code.item()]
        return self._state_cache.get(shared_state, shared_state)

    # setter
    # https://www.freecodecamp.org/news/python-property-decorator/

    @_state.setter
    def _state(self, new_state: State):
        self._shared_state_code[...] = ALL_STATES.index(new_state)
        if self._state in TERMINAL_STATES and \
            self._loop is not None and \
                not self._aio_event.is_set():
            self._set_event_threadsafe()

    def _set_event_threadsafe(self):
        # 函数的目的是什么?
        # 不会写, 不会
        # 不会写
        try:
            running_loop = asyncio.get_running_loop()
            # Return the running event loop in the current OS thread.
            #
            # If there is no running event loop a RuntimeError is raised. 
            # This function can only be called from a coroutine or a callback.
            # https://docs.python.org/3/library/asyncio-eventloop.html            
        except RuntimeError:
            running_loop = None

        async def _event_setter():
            self._aio_event.set()

        # 如下都是对 self._loop 做判断. 
        if self._loop.is_closed():
            return  # do nothing, the loop is already closed

        elif self._loop.is_running() and running_loop == self._loop:
            asyncio.create_task(_event_setter())
            # It submits the coroutine to run "in the background", in this example, it is 
            # _event_setter() function.
            # i.e.  
            # concurrently with the current task and all other tasks, switching between them at 
            # await points. It returns an awaitable handle called a "task" which you 
            # can also use to cancel the execution of the coroutine.
            # It's one of the central primitives of asyncio, the asyncio equivalent 
            # of starting a thread. (In the same analogy, awaiting the task with 
            # await is the equivalent of joining a thread.)
            # https://stackoverflow.com/questions/62528272/what-does-asyncio-create-task-do

        elif self._loop.is_running() and running_loop != self._loop:
            asyncio.run_coroutine_threadsafe(_event_setter(), self._loop)
            # 不会
            # asyncio 都不会. 

        else:
            self._loop.run_until_complete(_event_setter())
            # 

    @classmethod
    def _initialize_mpfuture_backend(cls):
        # 为什么要这个函数?
        # 这个函数是干什么的?
        
        pid = os.getpid()
        # 测试:
        # pid
        # 2145657
                
        logger.debug(f"Initializing MPFuture backend for pid {pid}")

        receiver_pipe, cls._global_sender_pipe = mp.Pipe(duplex=False)
        # cls._global_sender_pipe 的意思是谁都可以发是吗?
        
        cls._active_pid, cls._active_futures = pid, {}
        # cls._active_pid 就是本 pid
        
        # start the thread, launch the function: cls._process_updates_in_background
        cls._pipe_waiter_thread = threading.Thread(
            target=cls._process_updates_in_background, 
            args=[receiver_pipe], 
            name=f"{__name__}.BACKEND", 
            daemon=True
        )
        # cls._pipe_waiter_thread 是 
        # cls._pipe_waiter_thread
        # <Thread(hivemind.utils.mpfuture.BACKEND, started daemon 140184976451328)>
        # 
        # __name__
        # 'hivemind.utils.mpfuture'
        
        cls._pipe_waiter_thread.start()

    @staticmethod
    def reset_backend():
        """Last-resort function to reset internals of MPFuture. All current MPFuture instances will be broken"""
        MPFuture._active_pid = None
        MPFuture._initialization_lock = mp.Lock()
        MPFuture._update_lock = mp.Lock()
        SharedBytes._lock = mp.Lock()

    # 这个函数被一个 thread 启动了, 是在 __init__ 里面启动的. 函数里面有一个 loop: while True, infinite loop.
    # 这个函数做了 
    # - future.set_result
    # - future.set_exception
    # - future.cancel 
    # 等事情. 
    @classmethod
    def _process_updates_in_background(cls, receiver_pipe: mp.connection.Connection):
        # 多线程的 mp.connection.Connection 语法
        # https://docs.python.org/3/library/multiprocessing.html#multiprocessing.connection.Connection
        
        # Connection Objects
        # Connection objects allow the sending and receiving of picklable objects or strings. 
        # They can be thought of as message oriented connected sockets.
        # Connection objects are usually created using Pipe – see also Listeners and Clients.
        
        # receiver_pipe 是在 _initialize_mpfuture_backend 里.
        # receiver_pipe, cls._global_sender_pipe = mp.Pipe(duplex=False)
        # type(receiver_pipe)
        # <class 'multiprocessing.connection.Connection'>
        
        pid = os.getpid()
        
        while True:
            try:
                if cls._pipe_waiter_thread is not threading.current_thread():
                    # why this ?
                    break  # backend was reset, a new background thread has started
                # threading.current_thread()
                # <Thread(hivemind.utils.mpfuture.BACKEND, started daemon 140184976451328)>

                # cls._pipe_waiter_thread
                # <Thread(hivemind.utils.mpfuture.BACKEND, started daemon 140184976451328)>
                # 两者相同
                
                uid, update_type, payload = receiver_pipe.recv()
                # Who send you info?
                # this function: _send_update

                future = None
                future_ref = cls._active_futures.pop(uid, None)
                if future_ref is not None:
                    future = future_ref()

                if future is None:
                    # The MPFuture instance is already destroyed in this process
                    # (the caller is not interested in the result)
                    continue
                if update_type == UpdateType.RESULT:
                    future.set_result(payload)
                elif update_type == UpdateType.EXCEPTION:
                    future.set_exception(payload)
                elif update_type == UpdateType.CANCEL:
                    future.cancel()
                else:
                    raise RuntimeError(f"Received unexpected update type {update_type}")
            except (BrokenPipeError, EOFError, ConnectionError):
                logger.debug(f"Update pipe was was shut down unexpectedly (pid={pid})")
            except Exception as e:
                logger.exception(f"Could not retrieve update: caught {repr(e)} (pid={pid})")


    def _send_update(self, update_type: UpdateType, payload: Any = None):
        # _xxx 表示内部调用
        # yyy 表示对外调用

        # Who calls this function?
        # _send_update
        # - set_result
        # - set_exception
        # - cancel        
        """This method sends result, exception or cancel to the MPFuture origin."""
        try:
            with MPFuture._update_lock if self._use_lock else nullcontext():
                self._sender_pipe.send((self._uid, update_type, payload))

        except (ConnectionError, BrokenPipeError, EOFError, OSError) as e:
            logger.debug(f"No updates were sent: pipe to origin process was broken ({e}).", exc_info=True)


    def set_result(self, result: ResultType):
        # 这个是核心
        
        # 也就是只有 origin process 才能 set_result
        # 如果不是的话, 进入第三个分支.
        if os.getpid() == self._origin_pid:
            super().set_result(result)
            # set_result API: https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.set_result
            # Sets the result of the work associated with the Future to result.
            MPFuture._active_futures.pop(self._uid, None)
        
            # def set_result(self, result):
            #     """Sets the return value of work associated with the future.

            #     Should only be used by Executor implementations and unit tests.
            #     """
            #     with self._condition:
            #         if self._state in {CANCELLED, CANCELLED_AND_NOTIFIED, FINISHED}:
            #             raise InvalidStateError('{}: {!r}'.format(self._state, self))
            #         self._result = result
            #         self._state = FINISHED        # <= 会结束.
            #         for waiter in self._waiters:
            #             waiter.add_result(self)
            #         self._condition.notify_all()
            #     self._invoke_callbacks()
            
        elif self._state in TERMINAL_STATES:
            raise InvalidStateError(f"Can't set_result to a future that is {self._state} ({self._uid})")
        else:
            self._state_cache[self._state], self._result = base.FINISHED, result
            self._send_update(UpdateType.RESULT, result)


    def set_exception(self, exception: Optional[BaseException]):
        # 也就是只有 origin process 才能 set_result
        # 如果不是的话, 进入第三个分支.
        if os.getpid() == self._origin_pid:
            super().set_exception(exception)
            MPFuture._active_futures.pop(self._uid, None)
        elif self._state in TERMINAL_STATES:
            raise InvalidStateError(f"Can't set_exception to a future that is {self._state} ({self._uid})")
        else:
            self._state_cache[self._state], self._exception = base.FINISHED, exception
            self._send_update(UpdateType.EXCEPTION, exception)

    def cancel(self) -> bool:
        """
        Attempt to cancel the call. If the call is currently being executed or finished 
        running and cannot be cancelled then the method will return False, otherwise 
        the call will be cancelled and the method will return True.
        https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.cancel
        """
        if os.getpid() == self._origin_pid:
            MPFuture._active_futures.pop(self._uid, None)
            return super().cancel()
        elif self._state in [base.RUNNING, base.FINISHED]:
            return False
        else:
            self._state_cache[self._state] = base.CANCELLED
            self._send_update(UpdateType.CANCEL)
            return True

    def set_running_or_notify_cancel(self):
        if self._state == base.PENDING:
            self._state = base.RUNNING
            return True
        elif self._state == base.CANCELLED:
            return False
        else:
            raise InvalidStateError(
                f"Can't set_running_or_notify_cancel when future is in {self._state} ({self._uid})"
            )

    def result(self, timeout: Optional[float] = None) -> ResultType:
        if self._state not in TERMINAL_STATES:
            if os.getpid() != self._origin_pid:
                raise RuntimeError("Only the process that created MPFuture can await result")
            return super().result(timeout)
            # note:    
            # super().result(timeout)
            # https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.Future.result
            
        elif self._state == base.CANCELLED:
            raise base.CancelledError()
        elif self._exception:
            raise self._exception
        else:
            return self._result

    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        if self._state not in TERMINAL_STATES:
            if os.getpid() != self._origin_pid:
                raise RuntimeError("Only the process that created MPFuture can await exception")
            return super().exception(timeout)
        elif self._state == base.CANCELLED:
            raise base.CancelledError()
        return self._exception

    def done(self) -> bool:
        return self._state in TERMINAL_STATES

    def running(self):
        return self._state == base.RUNNING

    def cancelled(self):
        return self._state == base.CANCELLED

    def add_done_callback(self, callback: Callable[[MPFuture], None]):
        if os.getpid() != self._origin_pid:
            raise RuntimeError("Only the process that created MPFuture can set callbacks")
        return super().add_done_callback(callback)

    def __await__(self):
        if not self._aio_event:
            raise RuntimeError("Can't await: MPFuture was created with no event loop")

        yield from self._aio_event.wait().__await__()
        # 不懂
        
        try:
            return super().result()
        except base.CancelledError:
            raise asyncio.CancelledError()

    def __del__(self):
        if getattr(self, "_origin_pid", None) == os.getpid():
            MPFuture._active_futures.pop(self._uid, None)
        if getattr(self, "_aio_event", None):
            self._aio_event.set()

    def __getstate__(self):
        return dict(
            _sender_pipe=self._sender_pipe,
            _shared_state_code=self._shared_state_code,
            _origin_pid=self._origin_pid,
            _uid=self._uid,
            _use_lock=self._use_lock,
            _result=self._result,
            _exception=self._exception,
        )

    def __setstate__(self, state):
        self._sender_pipe = state["_sender_pipe"]
        self._shared_state_code = state["_shared_state_code"]
        self._origin_pid, self._uid = state["_origin_pid"], state["_uid"]
        self._result, self._exception = state["_result"], state["_exception"]
        self._use_lock = state["_use_lock"]

        self._waiters, self._done_callbacks = [], []
        self._condition = threading.Condition()
        self._aio_event, self._loop = None, None
        self._state_cache = {}
