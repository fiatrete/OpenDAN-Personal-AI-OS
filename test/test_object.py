import sys
import os
import logging

dir_path = os.path.dirname(os.path.realpath(__file__))
print(dir_path)

sys.path.append("{}/../src/".format(dir_path))
print(sys.path)

root = logging.getLogger()
root.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
root.addHandler(handler)


from knowledge import ObjectID, HashValue, EmailObjectBuilder
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

        email_folder = "F:\\system\\Downloads\\8081ffdb80925f5bff9c6ab9c4756c7d"
        email_object = EmailObjectBuilder({}, email_folder).build()
        
if __name__ == "__main__":
    unittest.main()
