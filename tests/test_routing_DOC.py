import debugpy

debugpy.listen(5678)
debugpy.wait_for_client()
debugpy.breakpoint()


"""
variable DHTKey
variable Subkey
variable DHTValue
variable BinaryDHTID
variable BinaryDHTValue


class RoutingTable
	method __init__
		variable node_id
		variable bucket_size
		variable depth_modulo
  
  
	method get_bucket_index
		variable node_id
		variable lower_index
		variable upper_index
		variable pivot_index
  
  
	method add_or_update_node
		variable node_id
		variable peer_id
		variable bucket_index
		variable bucket
		variable store_success
  
  
	method split_bucket
		variable index
		variable first
		variable second
  
  
	method get
		variable node_id
		variable peer_id
		variable default
  
  
	method __getitem__
		variable item
  
  
	method __setitem__
		variable node_id
		variable peer_id
  
  
	method __contains__
		variable item
  
  
	method __delitem__
		variable node_id
		variable node_peer_id
  
  
	method get_nearest_neighbors
		variable query_id
		variable k
		variable exclude
		variable candidates
		variable nearest_index
		variable nearest_bucket
		variable node_id
		variable peer_id
		variable left_index
		variable right_index
		variable current_lower
		variable current_upper
		variable current_depth
		variable split_direction
		variable heap_top
  
  
	method __repr__
		variable bucket_info
  
  
	variable node_id
	variable bucket_size
	variable depth_modulo
	variable buckets
	variable peer_id_to_uid
	variable uid_to_peer_id
 
 
class KBucket
	method __init__
		variable lower
		variable upper
		variable size
		variable depth
  
  
	method has_in_range
		variable node_id

	method add_or_update_node
		variable node_id
		variable peer_id

	method request_ping_node
		variable uid
		variable peer_id

	method __getitem__
		variable node_id

	method __delitem__
		variable node_id
		variable newnode_id
		variable newnode

	method split
		variable midpoint
		variable left
		variable right
		variable node_id
		variable peer_id
		variable bucket
  
	method __repr__
	variable lower
	variable upper
	variable size
	variable depth
	variable nodes_to_peer_id
	variable replacement_nodes
	variable nodes_requested_for_ping
	variable last_updated


class DHTID
	constant HASH_FUNC
	constant HASH_NBYTES
	constant RANGE
	constant MIN
	constant MAX

	method __new__ ✅ 
		variable value
  
	method generate ✅ 
		variable source
		variable nbits
		variable raw_uid
  
	method xor_distance ✅ 
		variable other
  
	method longest_common_prefix_length
		variable ids
		variable ids_bits
  
	method to_bytes ✅ 
		variable length
		variable byteorder
		variable signed
  
	method from_bytes ✅ 
		variable raw
		variable byteorder
		variable signed
  
	method __repr__
 
	method __bytes__


"""


import heapq
import operator
import random
from itertools import chain, zip_longest

from hivemind import LOCALHOST
from hivemind.dht.routing import DHTID, RoutingTable


def test_ids_basic():
    # basic functionality tests
    for i in range(100):
        id1, id2 = DHTID.generate(), DHTID.generate()
        assert DHTID.MIN <= id1 < DHTID.MAX and DHTID.MIN <= id2 <= DHTID.MAX
        assert DHTID.xor_distance(id1, id1) == DHTID.xor_distance(id2, id2) == 0
        assert DHTID.xor_distance(id1, id2) > 0 or (id1 == id2)
        assert DHTID.from_bytes(bytes(id1)) == id1 and DHTID.from_bytes(id2.to_bytes()) == id2

test_ids_basic()

def test_ids_depth():
    for i in range(100):
        ids = [random.randint(0, 4096) for i in range(random.randint(1, 256))]
        ours = DHTID.longest_common_prefix_length(*map(DHTID, ids))

        ids_bitstr = ["".join(bin(bite)[2:].rjust(8, "0") for bite in uid.to_bytes(20, "big")) for uid in ids]
        reference = len(shared_prefix(*ids_bitstr))
        assert reference == ours, f"ours {ours} != reference {reference}, ids: {ids}"


def test_routing_table_basic():
    node_id = DHTID.generate()
    routing_table = RoutingTable(node_id, bucket_size=20, depth_modulo=5)
    added_nodes = []

    for phony_neighbor_port in random.sample(range(10000), 100):
        phony_id = DHTID.generate()
        routing_table.add_or_update_node(phony_id, f"{LOCALHOST}:{phony_neighbor_port}")
        assert phony_id in routing_table
        assert f"{LOCALHOST}:{phony_neighbor_port}" in routing_table
        assert routing_table[phony_id] == f"{LOCALHOST}:{phony_neighbor_port}"
        assert routing_table[f"{LOCALHOST}:{phony_neighbor_port}"] == phony_id
        added_nodes.append(phony_id)

    assert routing_table.buckets[0].lower == DHTID.MIN and routing_table.buckets[-1].upper == DHTID.MAX
    for bucket in routing_table.buckets:
        assert len(bucket.replacement_nodes) == 0, "There should be no replacement nodes in a table with 100 entries"
    assert 3 <= len(routing_table.buckets) <= 10, len(routing_table.buckets)

    random_node = random.choice(added_nodes)
    assert routing_table.get(node_id=random_node) == routing_table[random_node]
    dummy_node = DHTID.generate()
    assert (dummy_node not in routing_table) == (routing_table.get(node_id=dummy_node) is None)

    for node in added_nodes:
        found_bucket_index = routing_table.get_bucket_index(node)
        for bucket_index, bucket in enumerate(routing_table.buckets):
            if bucket.lower <= node < bucket.upper:
                break
        else:
            raise ValueError("Naive search could not find bucket. Universe has gone crazy.")
        assert bucket_index == found_bucket_index


def test_routing_table_parameters():
    for (bucket_size, modulo, min_nbuckets, max_nbuckets) in [
        (20, 5, 45, 65),
        (50, 5, 35, 45),
        (20, 10, 650, 800),
        (20, 1, 7, 15),
    ]:
        node_id = DHTID.generate()
        routing_table = RoutingTable(node_id, bucket_size=bucket_size, depth_modulo=modulo)
        for phony_neighbor_port in random.sample(range(1_000_000), 10_000):
            routing_table.add_or_update_node(DHTID.generate(), f"{LOCALHOST}:{phony_neighbor_port}")
        for bucket in routing_table.buckets:
            assert len(bucket.replacement_nodes) == 0 or len(bucket.nodes_to_peer_id) <= bucket.size
        assert (
            min_nbuckets <= len(routing_table.buckets) <= max_nbuckets
        ), f"Unexpected number of buckets: {min_nbuckets} <= {len(routing_table.buckets)} <= {max_nbuckets}"


def test_routing_table_search():
    for table_size, lower_active, upper_active in [(10, 10, 10), (10_000, 800, 1100)]:
        node_id = DHTID.generate()
        routing_table = RoutingTable(node_id, bucket_size=20, depth_modulo=5)
        num_added = 0
        total_nodes = 0

        for phony_neighbor_port in random.sample(range(1_000_000), table_size):
            routing_table.add_or_update_node(DHTID.generate(), f"{LOCALHOST}:{phony_neighbor_port}")
            new_total = sum(len(bucket.nodes_to_peer_id) for bucket in routing_table.buckets)
            num_added += new_total > total_nodes
            total_nodes = new_total
        num_replacements = sum(len(bucket.replacement_nodes) for bucket in routing_table.buckets)

        all_active_neighbors = list(chain(*(bucket.nodes_to_peer_id.keys() for bucket in routing_table.buckets)))
        assert lower_active <= len(all_active_neighbors) <= upper_active
        assert len(all_active_neighbors) == num_added
        assert num_added + num_replacements == table_size

        # random queries
        for i in range(1000):
            k = random.randint(1, 100)
            query_id = DHTID.generate()
            exclude = query_id if random.random() < 0.5 else None
            our_knn, our_peer_ids = zip(*routing_table.get_nearest_neighbors(query_id, k=k, exclude=exclude))
            reference_knn = heapq.nsmallest(k, all_active_neighbors, key=query_id.xor_distance)
            assert all(our == ref for our, ref in zip_longest(our_knn, reference_knn))
            assert all(our_peer_id == routing_table[our_node] for our_node, our_peer_id in zip(our_knn, our_peer_ids))

        # queries from table
        for i in range(1000):
            k = random.randint(1, 100)
            query_id = random.choice(all_active_neighbors)
            our_knn, our_peer_ids = zip(*routing_table.get_nearest_neighbors(query_id, k=k, exclude=query_id))

            reference_knn = heapq.nsmallest(k + 1, all_active_neighbors, key=query_id.xor_distance)
            if query_id in reference_knn:
                reference_knn.remove(query_id)
            assert len(our_knn) == len(reference_knn)
            assert all(
                query_id.xor_distance(our) == query_id.xor_distance(ref)
                for our, ref in zip_longest(our_knn, reference_knn)
            )
            assert routing_table.get_nearest_neighbors(query_id, k=k, exclude=None)[0][0] == query_id


def shared_prefix(*strings: str):
    for i in range(min(map(len, strings))):
        if len(set(map(operator.itemgetter(i), strings))) != 1:
            return strings[0][:i]
    return min(strings, key=len)
