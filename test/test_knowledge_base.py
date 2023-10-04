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
from aios_kernel import KnowledgeBase, AgentPrompt, OpenAI_ComputeNode, ComputeKernel
import asyncio
import unittest

async def test_embedding_email(test):
    open_ai_node = OpenAI_ComputeNode()
    open_ai_node.start()
    ComputeKernel().add_compute_node(open_ai_node)
      
    email_folder = os.path.join(dir_path, "../rootfs/data/email/")
    print("explore emails in folder ", email_folder)
    for root, dirs, files in os.walk(email_folder):
        for dir in dirs:    
            email_object = EmailObjectBuilder({}, os.path.join(root, dir)).build()
            await KnowledgeBase().insert_object(email_object)

    msg_prompt = AgentPrompt()
    msg_prompt.messages = [{"role":"user","content":"abcdef"}]
       
    await KnowledgeBase().query_prompt(msg_prompt)

   

class TestKnowledgeBase(unittest.TestCase):
    def test_embedding(self):
        asyncio.run(test_embedding_email(self))
        
        
if __name__ == "__main__":
    unittest.main()
