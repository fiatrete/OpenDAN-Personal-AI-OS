import sys
import os

dir_path = os.path.dirname(os.path.realpath(__file__))
print(dir_path)

sys.path.append("{}/../src/".format(dir_path))
print(sys.path)

from knowledge import ChunkTracker, ChunkID, HashValue, PositionType


import asyncio
import unittest


class TestChunk(unittest.TestCase):
    def test_chunk_tracker(self):
        tracker = ChunkTracker()
        
        hash = HashValue.hash_data("1234567890".encode("utf-8"));
        cid = ChunkID.new_chunk_id(hash)
        print(cid)
            
        tracker.add_position(cid, "/tmp/1", PositionType.File)
        ret = tracker.get_position(cid)
        print(ret[0])
        
        tracker.remove_position(cid)
        ret = tracker.get_position(cid)
        self.assertEqual(ret, None)
    


if __name__ == "__main__":
    unittest.main()
