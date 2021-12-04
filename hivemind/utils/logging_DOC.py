"""
1. 

"""

import logging
import os
import sys
import threading
from enum import Enum
from typing import Optional, Union

# 默认的就是 logging.WARNING level 了. 
logging.addLevelName(logging.WARNING, "WARN")

loglevel = os.getenv("HIVEMIND_LOGLEVEL", "INFO")

_env_colors = os.getenv("HIVEMIND_COLORS")
if _env_colors is not None:
    use_colors = _env_colors.lower() == "true"
else:
    use_colors = sys.stderr.isatty()


class HandlerMode(Enum):
    NOWHERE = 0
    IN_HIVEMIND = 1
    IN_ROOT_LOGGER = 2


_init_lock = threading.RLock()
# 用锁的地方都是为了避免多线程的冲突
# 第一次比如从 mpfuture.py 里面用到了 get_logger 后
# 就能够初始化这个 _init_lock 

_current_mode = HandlerMode.IN_HIVEMIND
_default_handler = None


class TextStyle:
    """
    ANSI escape codes. Details: https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
    """

    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    BLUE = "\033[34m"
    PURPLE = "\033[35m"
    ORANGE = "\033[38;5;208m"  # From 8-bit palette

    if not use_colors:
        # Set the constants above to empty strings
        _codes = locals()
        _codes.update({_name: "" for _name in list(_codes) if _name.isupper()})


class CustomFormatter(logging.Formatter):
    """
    A formatter that allows a log time and caller info to be overridden via
    ``logger.log(level, message, extra={"origin_created": ..., "caller": ...})``.
    """

    # Details: https://en.wikipedia.org/wiki/ANSI_escape_code#Colors
    _LEVEL_TO_COLOR = {
        logging.DEBUG: TextStyle.PURPLE,
        logging.INFO: TextStyle.BLUE,
        logging.WARNING: TextStyle.ORANGE,
        logging.ERROR: TextStyle.RED,
        logging.CRITICAL: TextStyle.RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        if hasattr(record, "origin_created"):
            record.created = record.origin_created
            record.msecs = (record.created - int(record.created)) * 1000

        if not hasattr(record, "caller"):
            record.caller = f"{record.name}.{record.funcName}:{record.lineno}"

        # Aliases for the format argument
        record.levelcolor = self._LEVEL_TO_COLOR[record.levelno]
        record.bold = TextStyle.BOLD    # KeyError: 'bold' if I comment it, 所以这个 attribute 是自定义的.
        record.reset = TextStyle.RESET

        return super().format(record)


def _initialize_if_necessary():
    """
    如果是我来些这个函数名, 我会写 init_handler_if_necessary()
    """
    # 第一次会进入 logging.StreamHandler(), 第二次不会.
    global _current_mode, _default_handler

    with _init_lock:
        
        # 第二次不会进入
        if _default_handler is not None:
            return

        # 第一次会进入
        formatter = CustomFormatter(
            fmt="{asctime}.{msecs:03.0f} [{bold}{levelcolor}{levelname}{reset}] [{bold}{caller}{reset}] {message}",
            style="{",
            datefmt="%b %d %H:%M:%S",
        )
        """
        formatter
        
        <lego.utils.custom_logging.CustomFormatter object at 0x7faae3c0d610>
        special variables:
        function variables:
        
        datefmt: '%b %d %H:%M:%S'
        default_msec_format: '%s,%03d'
        default_time_format: '%Y-%m-%d %H:%M:%S'
        _LEVEL_TO_COLOR: {10: '\x1b[35m', 20: '\x1b[34m', 30: '\x1b[38;5;208m', 40: '\x1b[31m', 50: '\x1b[31m'}
        _fmt: '{asctime}.{msecs:03.0f} [{bold}{levelcolor}{levelname}{reset}] [{bold}{caller}{reset}] {message}'
        _style: <logging.StrFormatStyle object at 0x7faae3c0d040>
        """
        
        _default_handler = logging.StreamHandler()
        _default_handler.setFormatter(formatter)

        # 这个 logger name 只会被调用一次.
        # 名字定死了.
        _enable_default_handler("hivemind")


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Same as ``logging.getLogger()`` but ensures that the default hivemind log handler is initialized.

    :note: By default, the hivemind log handler (that reads the ``HIVEMIND_LOGLEVEL`` env variable and uses
           the colored log formatter) is only applied to messages logged inside the hivemind package.
           If you want to extend this handler to other loggers in your application, call
           ``use_hivemind_log_handler("in_root_logger")``.
    """
    # 你会发现展开来写是不行的, 因为有的地方返回值有限定
    _initialize_if_necessary()
    
    # logging.getLogger
    # create logger with "name"
    # https://docs.python.org/3/howto/logging-cookbook.html        
    return logging.getLogger(name)


def _enable_default_handler(name: str) -> None:
    """
    name
    'hivemind'
    
    logger
    <Logger hivemind (WARN)>
    
    loglevel
    'INFO'
    """
    logger = get_logger(name)
    logger.addHandler(_default_handler)
    logger.propagate = False
    logger.setLevel(loglevel)


def _disable_default_handler(name: str) -> None:
    logger = get_logger(name)
    logger.removeHandler(_default_handler)
    logger.propagate = True
    logger.setLevel(logging.NOTSET)


def use_hivemind_log_handler(where: Union[HandlerMode, str]) -> None:
    """
    Choose loggers where the default hivemind log handler is applied. Options for the ``where`` argument are:

    * "in_hivemind" (default): Use the hivemind log handler in the loggers of the ``hivemind`` package.
                               Don't propagate their messages to the root logger.
    * "nowhere": Don't use the hivemind log handler anywhere.
                 Propagate the ``hivemind`` messages to the root logger.
    * "in_root_logger": Use the hivemind log handler in the root logger
                        (that is, in all application loggers until they disable propagation to the root logger).
                        Propagate the ``hivemind`` messages to the root logger.

    The options may be defined as strings (case-insensitive) or values from the HandlerMode enum.
    """

    global _current_mode

    if isinstance(where, str):
        # We allow `where` to be a string, so a developer does not have to import the enum for one usage
        where = HandlerMode[where.upper()]

    _initialize_if_necessary()

    if where == _current_mode:
        return

    if _current_mode == HandlerMode.IN_HIVEMIND:
        _disable_default_handler("hivemind")
    elif _current_mode == HandlerMode.IN_ROOT_LOGGER:
        _disable_default_handler(None)

    _current_mode = where

    if _current_mode == HandlerMode.IN_HIVEMIND:
        _enable_default_handler("hivemind")
    elif _current_mode == HandlerMode.IN_ROOT_LOGGER:
        _enable_default_handler(None)


def golog_level_to_python(level: str) -> int:
    level = level.upper()
    if level in ["DPANIC", "PANIC", "FATAL"]:
        return logging.CRITICAL

    level = logging.getLevelName(level)
    if not isinstance(level, int):
        raise ValueError(f"Unknown go-log level: {level}")
    return level


def python_level_to_golog(level: str) -> str:
    if not isinstance(level, str):
        raise ValueError("`level` is expected to be a Python log level in the string form")

    if level == "CRITICAL":
        return "FATAL"
    if level == "WARNING":
        return "WARN"
    return level
