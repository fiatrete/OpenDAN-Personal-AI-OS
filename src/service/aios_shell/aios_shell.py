# aiso shell like bash for linux
import asyncio
import sys
import os
import logging
import re

from typing import Any, Optional, TypeVar, Tuple, Sequence
import argparse


from prompt_toolkit import HTML, PromptSession, prompt,print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.selection import SelectionState
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style

shell_style = Style.from_dict({
    'title': '#87d7ff bold', #RGB
    'content': '#007f00 bold',
    'prompt': '#00FF00',
})


directory = os.path.dirname(__file__)
sys.path.append(directory + '/../../')
from aios_kernel import Workflow,AIAgent,AgentMsg,AgentMsgState,ComputeKernel,OpenAI_ComputeNode,AIBus,AIChatSession

sys.path.append(directory + '/../../component/')
from agent_manager import AgentManager
from workflow_manager import WorkflowManager



class AIOS_Shell:
    def __init__(self,username:str) -> None:
        self.username = username
        self.current_target = "_"
        self.current_topic = "default"

    async def _handle_no_target_msg(self,bus:AIBus,msg:AgentMsg) -> bool:
        target_id = msg.target.split(".")[0]
        agent : AIAgent = await AgentManager().get(target_id)
        if agent is not None:
            bus.register_message_handler(target_id,agent._process_msg)
            return True
        
        a_workflow = await WorkflowManager().get_workflow(target_id)
        if a_workflow is not None:
            bus.register_message_handler(target_id,a_workflow._process_msg)
            return True
        
        return False
    
    async def is_agent(self,target_id:str) -> bool:
        agent : AIAgent = await AgentManager().get(target_id)
        if agent is not None:
            return True
        else:
            return False

    async def initial(self) -> bool:
        AgentManager().initial(os.path.abspath(directory + "/../../../rootfs/"))
        WorkflowManager().initial(os.path.abspath(directory + "/../../../rootfs/workflows/"))
        open_ai_node = OpenAI_ComputeNode()
        open_ai_node.start()
        ComputeKernel().add_compute_node(open_ai_node)
        AIBus().get_default_bus().register_unhandle_message_handler(self._handle_no_target_msg)
        return True 
        

    def get_version(self) -> str:
        return "0.0.1"

    async def send_msg(self,msg:str,target_id:str,topic:str,sender:str = None) -> str:
        agent_msg = AgentMsg()
        agent_msg.set(sender,target_id,msg)
        agent_msg.topic = topic
        resp = await AIBus.get_default_bus().send_message(target_id,agent_msg)
        if resp is not None:
            return resp.body
        else:
            return "error!"

    async def install_workflow(self,workflow_id:Workflow) -> None:
        pass

    async def call_func(self,func_name, args):
        match func_name:
            case 'send':
                target_id = args[0]
                msg_content = args[1]
                topic = args[2]
                resp = await self.send_msg(msg_content,target_id,topic,self.username)
                show_text = FormattedText([("class:title", f"{self.current_topic}@{self.current_target} >>> "),
                                           ("class:content", resp)])
                return show_text
            case 'open':
                if len(args) >= 1:
                    target_id = args[0]
                if len(args) >= 2:
                    topic = args[1]

                self.current_target = target_id
                self.current_topic = topic
                show_text = FormattedText([("class:title", f"current session switch to {topic}@{target_id}")])
                return show_text
            case 'history':
                num = 10
                offset = 0
                if args is not None:
                    if len(args) >= 1:
                        num = args[0]
                    if len(args) >= 2:
                        offset = args[1]

                db_path = ""
                if await self.is_agent(self.current_target):
                    db_path = AgentManager().db_path
                else:
                    db_path = WorkflowManager().db_file
                chatsession:AIChatSession = AIChatSession.get_session(self.current_target,f"{self.username}#{self.current_topic}",db_path,False)
                if chatsession is not None:
                    msgs = chatsession.read_history(num,offset)
                    format_texts = []
                    for msg in reversed(msgs):
                        format_texts.append(("class:content",f"{msg.sender} >>> {msg.body}"))
                        format_texts.append(("",f"\n-------------------\n"))
                    return FormattedText(format_texts)
                return FormattedText([("class:title", f"chatsession not found")])
            case 'exit':
                os._exit(0)
            case 'help':
                return FormattedText([("class:title", f"help~~~")])


#######################################################################################    
history = FileHistory('history.txt')
session = PromptSession(history=history) 

def parse_function_call(func_string):
    match = re.search(r'\s*(\w+)\s*\(\s*(.*)\s*\)\s*', func_string)
    if not match:
        return None

    func_name = match.group(1)
    params_string = match.group(2).strip()    
    params = re.split(r'\s*,\s*(?=(?:[^"]*"[^"]*")*[^"]*$)', params_string)
    params = [param.strip('"') for param in params]
    if len(params[0]) == 0:
        params = None

    return func_name, params
    

async def main():
    print("aios shell prepareing...")
    logging.basicConfig(filename="aios_shell.log",filemode="w",encoding='utf-8',
                        level=logging.INFO,
                        format='[%(asctime)s]%(name)s[%(levelname)s]: %(message)s')
    shell = AIOS_Shell("user")
    await shell.initial()

    s = """了解。首先，我们需要进行方案讨论，定出一致的活动策略。我将任务分解如下：
财务组： 分析可见的预算，提供一份合理并被执行的财务方案。
行程预订组： 硅谷自然迷人的地方众多，寻找适合11人秋游的地点，以及一个可行的周末日期。策划一个一天或两天的安排，包括选择有南瓜园的地方，采摘苹果，参观当地的酗酒作坊等秋游活动。
嘉宾对接组： 把个人的食品饮料或过敏食物的需求事先了解并计入行程内。
酒店预订组：根据行程预订组的日期安排，活动时间在1天还是2天，在这个之内找一个合适的住宿，试着保持让住宿在预算边界以内。
活动摄像组： 准备活动拍摄与剪辑方案。\n\n然后，我将把这些拆分后的任务发来小组。 
sendmsg(财务组,分析预算并提供一份财务方案.) 
sendmsg(行程预订组,找出适合秋游的地方和日期.) 
sendmsg(嘉宾对接组,了解个人的饮食需求.) 
sendmsg(酒店预订组,查询并预订住宿.) 
sendmsg(活动摄像组,提供活动拍摄方案.)  
经过一两天的准备，一切就绪之后，我将向工作人员发送最后的行程计划，
    """
    r = Workflow.prase_llm_result(s)
    print(f"aios shell {shell.get_version()} ready.")

    completer = WordCompleter(['send($target,$msg,$topic)', 
                               'open($target,$topic)', 
                               'history($num,$offset)',
                               'show()',
                               'exit()', 
                               'help()'], ignore_case=True)
  
    while True:
        user_input = await session.prompt_async(f"{shell.username}<->{shell.current_topic}@{shell.current_target}$",completer=completer,style=shell_style)
        if len(user_input) <= 1:
            continue

        func_call = parse_function_call(user_input)
        show_text = None
        if func_call:
            show_text = await shell.call_func(func_call[0], func_call[1])
        else:
            resp = await shell.send_msg(user_input,shell.current_target,shell.current_topic,shell.username)
            show_text = FormattedText([
                ("class:title", f"{shell.current_topic}@{shell.current_target} >>> "),
                ("class:content", resp)
            ])

        print_formatted_text(show_text,style=shell_style)
        #print_formatted_text(f"{shell.username}<->{shell.current_topic}@{shell.current_target} >>> {resp}",style=shell_style)

    

if __name__ == "__main__":    
    asyncio.run(main())

