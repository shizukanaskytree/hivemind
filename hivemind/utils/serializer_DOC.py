""" A unified interface for several common serialization methods """
from abc import ABC, abstractmethod
from typing import Any, Dict

import msgpack
# https://github.com/msgpack/msgpack-python

# Specification of msgpack
# https://github.com/msgpack/msgpack/blob/master/spec.md

from hivemind.utils.logging import get_logger

logger = get_logger(__name__)

# ABC
# abc — Abstract Base Classes ... 
# This module provides the infrastructure for defining abstract base classes (ABCs) in Python

class SerializerBase(ABC):
    @staticmethod
    @abstractmethod
    def dumps(obj: object) -> bytes:
        pass

    @staticmethod
    @abstractmethod
    def loads(buf: bytes) -> object:
        pass

# 没想到, 这么麻烦. 
# ---
# serializer = MSGPackSerializer  # used to pack/unpack DHT Values for transfer over network
# from hivemind/dht/protocol.py
# ---
# 
class MSGPackSerializer(SerializerBase):
    _ext_types: Dict[Any, int] = {}
    _ext_type_codes: Dict[int, Any] = {}
    _TUPLE_EXT_TYPE_CODE = 0x40

    # ext_serializable is used in tensor_descr.py 用于压缩 tensor
    # python tests/test_routing_DOC.py 就可以看到这个被使用的过程.
    # 单步 debug 的笔记可以看: https://www.notion.so/xiaofengwu/DHT-in-one-page-d3675d66f9394616b6395ce11ed97d31#d177575f24ac496b8be921b923701f2b
    # It is used in 
    # 1) hivemind/dht/storage.py:10:@MSGPackSerializer.ext_serializable(0x50)
    # 2) hivemind/utils/tensor_descr.py:67:@MSGPackSerializer.ext_serializable(0x51)
    @classmethod
    def ext_serializable(cls, type_code: int):
        assert isinstance(type_code, int), "Please specify a (unique) int type code"

        def wrap(wrapped_type: type):
            # 传进来是 wrapped_type, output is wrapped_type. nothing changed. 
            # However, the thing that processed is the registration or save 
            # sth inside two dict over the whole package system.
            
            assert callable(getattr(wrapped_type, "packb", None)) and callable(
                getattr(wrapped_type, "unpackb", None)
            ), f"Every ext_type must have 2 methods: packb(self) -> bytes and classmethod unpackb(cls, bytes)"

            if type_code in cls._ext_type_codes:
                logger.warning(f"{cls.__name__}: type {type_code} is already registered, overwriting.")
                
            cls._ext_type_codes[type_code], cls._ext_types[wrapped_type] = wrapped_type, type_code
            
            return wrapped_type

        return wrap

    # 这个函数只是作为一个
    @classmethod
    def _encode_ext_types(cls, obj):
        type_code = cls._ext_types.get(type(obj))
        if type_code is not None:
            return msgpack.ExtType(type_code, obj.packb())
        elif isinstance(obj, tuple):
            # Tuples need to be handled separately to ensure that
            # 1. tuple serialization works and 2. tuples serialized not as lists
            data = msgpack.packb(list(obj), strict_types=True, use_bin_type=True, default=cls._encode_ext_types)
            return msgpack.ExtType(cls._TUPLE_EXT_TYPE_CODE, data)
            # 1.
            # ExtType represents ext type in msgpack.
            
        return obj

    @classmethod
    def _decode_ext_types(cls, type_code: int, data: bytes):
        if type_code in cls._ext_type_codes:
            return cls._ext_type_codes[type_code].unpackb(data)
        elif type_code == cls._TUPLE_EXT_TYPE_CODE:
            return tuple(msgpack.unpackb(data, ext_hook=cls._decode_ext_types, raw=False))

        logger.warning(f"Unknown ExtType code: {type_code}, leaving it as is.")
        return data

    @classmethod
    def dumps(cls, obj: object) -> bytes:
        return msgpack.dumps(obj, use_bin_type=True, default=cls._encode_ext_types, strict_types=True)
    
    # 1. 
    # msgpack.dumps
    # https://msgpack-python.readthedocs.io/en/latest/api.html
    # Pack object o and return packed bytes
    # https://msgpack-python.readthedocs.io/en/latest/api.html#msgpack.Packer
    # 
    # default (callable) – Convert user type to builtin type that Packer supports. See also simplejson’s document.


    @classmethod
    def loads(cls, buf: bytes) -> object:
        return msgpack.loads(buf, ext_hook=cls._decode_ext_types, raw=False)
