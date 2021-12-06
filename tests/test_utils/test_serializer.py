"""
variable logger


class SerializerBase
	method dumps
		variable obj
	method loads
		variable buf
  
  
class MSGPackSerializer
	variable _ext_types
	variable _ext_type_codes
	constant _TUPLE_EXT_TYPE_CODE
 
	method ext_serializable
		variable type_code
		function wrap
			variable wrapped_type

	method _encode_ext_types
		variable obj
		variable type_code
		variable data

	method _decode_ext_types
		variable type_code
		variable data

	method dumps    # ✅ tests/test_routing.py
		variable obj

	method loads
		variable buf
"""


"""
# tests/test_routing.py, 去看这个文件, 这里会间接调用 serializer.py

def test_ids_basic():
    # basic functionality tests
    for i in range(100):
        id1, id2 = DHTID.generate(), DHTID.generate()
        assert DHTID.MIN <= id1 < DHTID.MAX and DHTID.MIN <= id2 <= DHTID.MAX
        assert DHTID.xor_distance(id1, id1) == DHTID.xor_distance(id2, id2) == 0
        assert DHTID.xor_distance(id1, id2) > 0 or (id1 == id2)
        assert DHTID.from_bytes(bytes(id1)) == id1 and DHTID.from_bytes(id2.to_bytes()) == id2

test_ids_basic()
"""

