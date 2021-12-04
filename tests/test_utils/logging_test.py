"""
我发现这个 logging 是没有 bug 的, 只是我不会用.

variable loglevel
variable _env_colors
variable use_colors

class HandlerMode ✅
	constant NOWHERE
	constant IN_HIVEMIND
	constant IN_ROOT_LOGGER
 
variable _init_lock
variable _current_mode
variable _default_handler

class TextStyle ✅
	constant RESET
	constant BOLD
	constant RED
	constant BLUE
	constant PURPLE
	constant ORANGE
	variable _codes
 
class CustomFormatter ✅
	constant _LEVEL_TO_COLOR
 
	method format
		variable record
  
function _initialize_if_necessary ✅
	variable formatter
 
function get_logger ✅
	variable name
 
function _enable_default_handler ✅
	variable name
	variable logger
 
function _disable_default_handler ✅
	variable name
	variable logger
 
function use_hivemind_log_handler ✅
	variable where
 
function golog_level_to_python
	variable level
 
function python_level_to_golog
	variable level
"""

# import debugpy

# debugpy.listen(5678)
# debugpy.wait_for_client()
# debugpy.breakpoint()

import unittest
import os
from hivemind.utils.logging import get_logger, CustomFormatter, use_hivemind_log_handler


def test_part1():
    logger = get_logger("hivemind") # 只有写成 "hivemind" 才有用
    # logger = get_logger(__name__) # 没用, comment this.
    # 测试不出来
    logger.warning('Watch out!')  # will print a message to the console
    logger.info('I told you so')  # will print anything

# test_part1() # 测出来了

def test_part2():
    # hivemind/hivemind_cli/run_server.py is another example to use logging correctly. 
    use_hivemind_log_handler("in_root_logger")
    logger = get_logger(__name__)
    logger.warning('Watch out in part2!')  # will print a message to the console
    logger.info('I told you so in part2.')  # will not print anything

# test_part2() # 测出来了
