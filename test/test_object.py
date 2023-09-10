import sys
import os

dir_path = os.path.dirname(os.path.realpath(__file__))
print(dir_path)

sys.path.append("{}/../src/".format(dir_path))
print(sys.path)

from knowledge import ObjectID, HashValue


import asyncio
import unittest


class TestVectorSTorage(unittest.TestCase):
    def test_object(self):
        data = HashValue.hash_data("1233".encode("utf-8"));
        print(data.to_base58())
        print(data.to_base36())
        
        data2 = HashValue.from_base58(data.to_base58())
        self.assertEqual(data.to_base36(), data2.to_base36())
        
        data2 = HashValue.from_base36(data.to_base36())
        self.assertEqual(data.to_base58(), data2.to_base58())


if __name__ == "__main__":
    unittest.main()
