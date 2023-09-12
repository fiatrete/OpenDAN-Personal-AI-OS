import sys
import os

dir_path = os.path.dirname(os.path.realpath(__file__))
print(dir_path)

sys.path.append("{}/../src/".format(dir_path))
print(sys.path)

from knowledge import ChromaVectorStore


import asyncio
import unittest


async def test_embedding_email():
    storage = ChromaVectorStore("test")
    await storage.insert([1, 2, 3], "test")
    ids = await storage.query([1, 2, 3], 10)
    print(ids)

class TestVectorSTorage(unittest.TestCase):
    def test_run(self):
        asyncio.run(test_vector())


if __name__ == "__main__":
    unittest.main()
