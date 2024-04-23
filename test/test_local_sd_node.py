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
from aios_kernel.local_stability_node import Local_Stability_ComputeNode
from aios_kernel.compute_task import ComputeTaskType, ComputeTask, ComputeTaskState

#to launch a local stability node, please check:
#https://github.com/glen0125/stable-diffusion-webui-docker

#os.environ["LOCAL_STABILITY_URL"] = "http://aigc:7860"
#os.environ["TEXT2IMG_DEFAULT_MODEL"] = "v1-5-pruned-emaonly"
#os.environ["TEXT2IMG_OUTPUT_DIR"] = "./"

@pytest.mark.asyncio
async def test_local_sd_node(propmt, model, negative_prompt):
    node = Local_Stability_ComputeNode.get_instance()
    if await node.initial() is not True:
        print("node initial failed!")
        return
    
    task = ComputeTask()
    task.task_type = ComputeTaskType.TEXT_2_IMAGE
    task.create_time = time.time()
    task.task_id = uuid.uuid4().hex
    task.params['model_name'] = model
    task.params['prompt'] = propmt
    task.params['negative_prompt'] = negative_prompt
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
    model = "v1-5-pruned-emaonly"
    negative_prompt = None
    if arg_len >= 2:
        prompt = os.sys.argv[1]
    if arg_len == 3:
        model = os.sys.argv[2]
    if arg_len == 4:
        negative_prompt = os.sys.argv[3]

    asyncio.run(test_local_sd_node(prompt, model, negative_prompt))
