# aiso shell like bash for linux
import asyncio
import sys
import os
import logging

from typing import Any, Optional, TypeVar, Tuple, Sequence
import argparse

from prompt_toolkit.formatted_text.base import AnyFormattedText
from prompt_toolkit import Application, PromptSession, prompt
from prompt_toolkit.selection import SelectionState
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter


directory = os.path.dirname(__file__)
sys.path.append(directory + '/../../')
from aios_kernel import Workflow,AIAgent,AgentMsg,AgentMsgState,ComputeKernel,OpenAI_ComputeNode,AIBus

sys.path.append(directory + '/../../component/')
from agent_manager import AgentManager
from workflow_manager import WorkflowManager


class AIOS_Shell:
    def __init__(self,username:str) -> None:
        self.username = username
        
        self.user_chatsession = {}

    async def _handle_no_target_msg(self,bus:AIBus,msg:AgentMsg) -> bool:
        agent : AIAgent = await AgentManager().get(msg.target)
        if agent is not None:
            bus.register_message_handler(msg.target,agent._process_msg)
            return True
        
        a_workflow = await WorkflowManager().get_workflow(msg.target)
        if a_workflow is not None:
            bus.register_message_handler(msg.target,a_workflow._process_msg)
            for subflow in a_workflow.sub_workflows.values():
                bus.register_message_handler(subflow.workflow_name,subflow._process_msg)
            return True
        
        return False
    

    async def initial(self) -> bool:
        AgentManager().initial(os.path.abspath(   directory + "/../../../rootfs/"))
        WorkflowManager().initial(os.path.abspath(directory + "/../../../rootfs/workflows/"))
        open_ai_node = OpenAI_ComputeNode()
        open_ai_node.start()
        ComputeKernel().add_compute_node(open_ai_node)
        AIBus().get_default_bus().register_unhandle_message_handler(self._handle_no_target_msg)
        return True 
        

    def get_version(self) -> str:
        return "0.0.1"

    async def send_msg(self,msg:str,target_id:str,sender:str = None) -> str:
        agent_msg = AgentMsg()
        agent_msg.set(sender,target_id,msg)
        agent_msg.topic = "default"
        resp = await AIBus().get_default_bus().send_message(target_id,agent_msg)
        if resp is not None:
            return resp.body
        else:
            return "error!"

    async def install_workflow(self,workflow_id:Workflow) -> None:
        pass
    

#######################################################################################    
def proc_input_by_agent():
    pass

def show_help():
    print("this is help")

history = FileHistory('history.txt')
session = PromptSession(history=history) 

async def main():
    print("aios shell prepareing...")
    logging.basicConfig(level=logging.INFO,format='[%(asctime)s]%(name)s[%(levelname)s]: %(message)s')
    shell = AIOS_Shell("user")
    await shell.initial()
    print(f"aios shell {shell.get_version()} ready.")

    completer = WordCompleter(['list agent', 'list workflow', 'exit', 'help'], ignore_case=True)
    #history = FileHistory('history.txt')
    while True:
        user_input = await session.prompt_async('>>> ',completer=completer)
        match user_input:
            case "list agent":
                print(AgentManager().list_agent())
            case "list workflow":
                print(WorkflowManager().list_workflow())
            case "help":
                show_help()
            case "exit":
                break
        

        if user_input.startswith("send"):
            args = user_input.split(" ")
            if len(args) < 3:
                print("send msg failed, usage: send target_id msg_content")
                continue
            target_id = args[1]
            msg_content = args[2]
            resp = await shell.send_msg(msg_content,target_id,shell.username)
            print(f"<<<{target_id} : {resp}")

if __name__ == "__main__":    
    asyncio.run(main())

