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
from aios_kernel import KnowledgeBase, AgentPrompt
import asyncio
import unittest

async def test_embedding_email():
    data = HashValue.hash_data("1233".encode("utf-8"));
    print(data.to_base58())
    print(data.to_base36())
    
    data2 = HashValue.from_base58(data.to_base58())
    self.assertEqual(data.to_base36(), data2.to_base36())
    
    data2 = HashValue.from_base36(data.to_base36())
    self.assertEqual(data.to_base58(), data2.to_base58())

    email_folder = "F:\\system\\Downloads\\8081ffdb80925f5bff9c6ab9c4756c7d"
    email_object = EmailObjectBuilder({}, email_folder).build()

    await KnowledgeBase().do_embedding(email_object)


async def test_query_email():
    msg_prompt = AgentPrompt()
    msg_prompt.messages = [{"role":"user","content":"abcdef"}]
       
    KnowledgeBase().query(msg_prompt)

class TestVectorSTorage(unittest.TestCase):
    def test_embedding(self):
        asyncio.run(test_embedding_email())

    def test_query(self):
        asyncio.run(test_query_email())
        
        
if __name__ == "__main__":
    unittest.main()
