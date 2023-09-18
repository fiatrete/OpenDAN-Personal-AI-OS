import sys
import os

dir_path = os.path.dirname(os.path.realpath(__file__))
print(dir_path)

sys.path.append("{}/../src/".format(dir_path))
print(sys.path)


import logging
import sys

root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
root.addHandler(handler)


from knowledge import (
    ChunkTracker,
    ChunkID,
    HashValue,
    PositionType,
    KnowledgeStore,
    ChunkListWriter,
)
import asyncio
import unittest


class TestChunk(unittest.TestCase):
    def test_chunk_tracker(self):
        tracker = KnowledgeStore().get_chunk_tracker()

        hash = HashValue.hash_data("1234567890".encode("utf-8"))
        cid = ChunkID.new_chunk_id(hash)
        print(cid)

        tracker.add_position(cid, "/tmp/1", PositionType.File)
        ret = tracker.get_position(cid)
        print(ret[0])

        tracker.remove_position(cid)
        ret = tracker.get_position(cid)
        self.assertEqual(ret, None)

    def test_chunk(self):
        gen = ChunkListWriter(
            KnowledgeStore().get_chunk_store(), KnowledgeStore().get_chunk_tracker()
        )
        gen.create_chunk_list_from_file("H:/test", 1024 * 1024, True)

        # Read the file
        text_file = "H:/test.txt"
        with open(text_file, "r", encoding="utf-8") as file:
            text = file.read()

        gen.create_chunk_list_from_text(text, 1024)


if __name__ == "__main__":
    unittest.main()
