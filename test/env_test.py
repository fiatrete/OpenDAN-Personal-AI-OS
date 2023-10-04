import asyncio
import os
import sys

directory = os.path.dirname(__file__)
sys.path.append(directory + '/../src')

from aios_kernel import CalenderEnvironment,WorkflowEnvironment


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


if __name__ == "__main__":
    #test_rstr = "abc is {abc}"
    #values = {"abc":"123"}
    #new_str = test_rstr.format_map(values)
    #print(new_str)

    asyncio.run(test_buildin_envs())