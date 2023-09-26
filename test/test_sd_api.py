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
from aios_kernel.stability_node import Stability_ComputeNode
from aios_kernel.compute_task import ComputeTaskType, ComputeTask, ComputeTaskState

os.environ["STABILITY_API_KEY"] = ""
os.environ["STABILITY_DEFAULT_MODEL"] = "stable-diffusion-512-v2-1"
os.environ["TEXT2IMG_OUTPUT_DIR"] = "./"

@pytest.mark.asyncio
async def test_sd_api(propmt, model):
    node = Stability_ComputeNode.get_instance()
    if await node.initial() is not True:
        print("node initial failed!")
        return
    
    task = ComputeTask()
    task.task_type = ComputeTaskType.TEXT_2_IMAGE
    task.create_time = time.time()
    task.task_id = uuid.uuid4().hex
    task.params['model_name'] = model
    task.params['prompt'] = propmt
    await node.push_task(task)

    while True:
        if task.state == ComputeTaskState.DONE:
            local_file = task.result.result
            print("local file is: ", local_file)
            break
        await asyncio.sleep(1)

     # result = node._run_task(task)
    # print("result is: ", result)

    # if result.result is not None:
    #     local_file = result.result
    #     print("local file is: ", local_file)

if __name__ == "__main__":
    arg_len = len(os.sys.argv)
    prompt = "a beautiful sunset"
    model = "stable-diffusion-512-v2-1"
    if arg_len >= 2:
        prompt = os.sys.argv[1]
    if arg_len == 3:
        model = os.sys.argv[2]

    asyncio.run(test_sd_api(prompt, model))
