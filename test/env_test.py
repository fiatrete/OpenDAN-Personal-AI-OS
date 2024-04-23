import asyncio
import os
import sys
directory = os.path.dirname(__file__)
sys.path.append(directory + '/../src')
from aios_kernel import CalenderEnvironment,WorkflowEnvironment,ComputeKernel,OpenAI_ComputeNode,AIStorage


async def test_buildin_envs():
    c_env = CalenderEnvironment("calender")
    c_env.start()
    print(c_env.get_value("now"))
    async def show_event(eventid,event):
        print(event.data)
    c_env.attach_event_handler("timer",show_event)

    w_env = WorkflowEnvironment("workflow",os.path.abspath(directory + "/../rootfs/workflow_env.db"))
    w_env.set_value("test","test_aaaa")
    print(w_env.get_value("test"))

    await asyncio.sleep(10)

async def test_image_to_text():
    # init the compute kernel and add the compute node
    open_ai_node = OpenAI_ComputeNode.get_instance()
    if await open_ai_node.initial() is not True:
        print("openai node initial failed!")
        return False
    ComputeKernel.get_instance().add_compute_node(open_ai_node)
    w_env = WorkflowEnvironment("workflow",os.path.abspath(directory + "/../rootfs/workflow_env.db"))
    assert w_env.functions['image_2_text'] is not None
    await ComputeKernel.get_instance().start()
    fn = w_env.get_ai_function('image_2_text')
    image_path = os.path.abspath(directory + "/test.png")
    arguments = {
        'image_path': image_path
    }

    # execute the ai function
    result = await fn.execute(**arguments)
    assert result is not ""
    print(result)

    await asyncio.sleep(10)


if __name__ == "__main__":
    #test_rstr = "abc is {abc}"
    #values = {"abc":"123"}
    #new_str = test_rstr.format_map(values)
    #print(new_str)

    # asyncio.run(test_buildin_envs())
    asyncio.run(test_image_to_text())