import os
import time
import uuid
import io
import asyncio
import sys
import logging
import pytest
directory = os.path.dirname(__file__)
sys.path.append(directory + '/../src')
from aios_kernel.dall_e_compute_node import DallE_ComputeNode
from aios_kernel.compute_task import ComputeTaskType, ComputeTask, ComputeTaskState

os.environ["TEXT2IMG_OUTPUT_DIR"] = "./"
os.environ["openai_api_key"] = ""

@pytest.mark.asyncio
async def test_dall_e_node(propmt, model):
    node = DallE_ComputeNode.get_instance()
    if await node.initial() is not True:
        print("node initial failed!")
        return
    
    task = ComputeTask()
    task.task_type = ComputeTaskType.TEXT_2_IMAGE
    task.create_time = time.time()
    task.task_id = uuid.uuid4().hex
    task.params['prompt'] = propmt
    await node.push_task(task)

    while True:
        if task.state == ComputeTaskState.DONE:
            local_file = task.result.result
            print("local file is: ", local_file)
            break
        await asyncio.sleep(1)

if __name__ == "__main__":
    arg_len = len(os.sys.argv)
    prompt = "a beautiful sunset"
    model = "dall-e-3"
    if arg_len >= 2:
        prompt = os.sys.argv[1]
    if arg_len == 3:
        model = os.sys.argv[2]

    asyncio.run(test_dall_e_node(prompt, model))
