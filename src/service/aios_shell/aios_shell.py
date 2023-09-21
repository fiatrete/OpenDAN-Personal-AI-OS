# aiso shell like bash for linux
import asyncio
import sys
import os
import logging
import re
import toml
import shlex

from typing import Any, Optional, TypeVar, Tuple, Sequence
import argparse


from prompt_toolkit import HTML, PromptSession, prompt,print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.selection import SelectionState
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style

directory = os.path.dirname(__file__)
sys.path.append(directory + '/../../')

from aios_kernel import AIOS_Version,UserConfigItem,AIStorage,Workflow,AIAgent,AgentMsg,AgentMsgStatus,ComputeKernel,OpenAI_ComputeNode,AIBus,AIChatSession,AgentTunnel,TelegramTunnel,CalenderEnvironment,Environment,EmailTunnel,LocalLlama_ComputeNode
import proxy

sys.path.append(directory + '/../../component/')
from agent_manager import AgentManager
from workflow_manager import WorkflowManager


logger = logging.getLogger(__name__)

shell_style = Style.from_dict({
    'title': '#87d7ff bold', #RGB
    'content': '#007f00', # resp content
    'prompt': '#00FF00',
    'error': '#8F0000 bold'
})


class AIOS_Shell:
    def __init__(self,username:str) -> None:
        self.username = username
        self.current_target = "_"
        self.current_topic = "default"
        self.is_working = True

    def declare_all_user_config(self):
        user_config = AIStorage.get_instance().get_user_config()
        user_config.add_user_config("username","username is your full name when using AIOS",False,None,)

        openai_node = OpenAI_ComputeNode.get_instance()
        openai_node.declare_user_config()

        user_config.add_user_config("shell.current","last opened target and topic",True,"default@Jarvis")
        proxy.declare_user_config()


    async def _handle_no_target_msg(self,bus:AIBus,msg:AgentMsg) -> bool:
        target_id = msg.target.split(".")[0]
        agent : AIAgent = await AgentManager.get_instance().get(target_id)
        if agent is not None:
            agent.owner_env = Environment.get_env_by_id("calender") 
            bus.register_message_handler(target_id,agent._process_msg)
            return True
        
        a_workflow = await WorkflowManager.get_instance().get_workflow(target_id)
        if a_workflow is not None:
            bus.register_message_handler(target_id,a_workflow._process_msg)
            return True
        
        return False
    
    async def is_agent(self,target_id:str) -> bool:
        agent : AIAgent = await AgentManager.get_instance().get(target_id)
        if agent is not None:
            return True
        else:
            return False

    async def initial(self) -> bool:
        cal_env = CalenderEnvironment("calender")
        await cal_env.start()
        Environment.set_env_by_id("calender",cal_env)
        
        await AgentManager.get_instance().initial()
        await WorkflowManager.get_instance().initial()

        open_ai_node = OpenAI_ComputeNode.get_instance()
        if await open_ai_node.initial() is not True:
            logger.error("openai node initial failed!")
            return False
        ComputeKernel.get_instance().add_compute_node(open_ai_node)
        
        llama_ai_node = LocalLlama_ComputeNode()
        await llama_ai_node.start()
        # ComputeKernel.get_instance().add_compute_node(llama_ai_node)

        await ComputeKernel.get_instance().start()

        AIBus().get_default_bus().register_unhandle_message_handler(self._handle_no_target_msg)
        AIBus().get_default_bus().register_message_handler(self.username,self._user_process_msg)

        TelegramTunnel.register_to_loader()
        EmailTunnel.register_to_loader()

        user_data_dir = AIStorage.get_instance().get_myai_dir()
        tunnels_config_path = os.path.abspath(f"{user_data_dir}/etc/tunnels.cfg.toml")
        tunnel_config = None
        try: 
            tunnel_config = toml.load(tunnels_config_path)
            if tunnel_config is not None:
                await AgentTunnel.load_all_tunnels_from_config(tunnel_config)
        except Exception as e:
            logger.warning(f"load tunnels config from {tunnels_config_path} failed!")
            
        return True 
        

    def get_version(self) -> str:
        return "0.5.1"

    async def send_msg(self,msg:str,target_id:str,topic:str,sender:str = None) -> str:
        agent_msg = AgentMsg()
        agent_msg.set(sender,target_id,msg)
        agent_msg.topic = topic
        resp = await AIBus.get_default_bus().send_message(agent_msg)
        if resp is not None:
            return resp.body
        else:
            return "error!"

    async def _user_process_msg(self,msg:AgentMsg) -> AgentMsg:
        pass



    async def get_tunnel_config_from_input(self,tunnel_target,tunnel_type):
        tunnel_config = {}
        tunnel_config["tunnel_id"] = f"{tunnel_type}_2_{tunnel_target}"
        tunnel_config["target"] = tunnel_target
        intpu_table = {}
        tunnel_introduce : str = ""
        match tunnel_type:
            case "telegram":
                tunnel_config["type"] = "TelegramTunnel"
                intpu_table["token"] = UserConfigItem("telegram bot token")
            case "email":
                tunnel_config["type"] = "EmailTunnel"
            case _:
                error_text = FormattedText([("class:error", f"tunnel type {tunnel_type}not support!")])    
                print_formatted_text(error_text,style=shell_style)
                return None

        intro_text = FormattedText([("class:prompt", tunnel_introduce)])    
        print_formatted_text(intro_text,style=shell_style)
        for key,item in intpu_table.items():
            user_input = await try_get_input(f"{key} : {item.desc}")
            if user_input is None:
                return None
            
            tunnel_config[key] = user_input   

        return tunnel_config
                 

    async def append_tunnel_config(self,tunnel_config):
        user_data_dir = AIStorage.get_instance().get_myai_dir()
        tunnels_config_path = os.path.abspath(f"{user_data_dir}/etc/tunnels.cfg.toml")
        try: 
            all_tunnels = toml.load(tunnels_config_path)
            if all_tunnels is not None:
                all_tunnels[tunnel_config["tunnel_id"]] = tunnel_config
                f = open(tunnels_config_path,"w")
                if f:
                    toml.dump(all_tunnels,f)
        except Exception as e:
            logger.warning(f"load tunnels config from {tunnels_config_path} failed!")

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
            case 'set_config':
                show_text = FormattedText([("class:title", f"set config failed!")])
                if len(args) == 1:
                    key = args[0]
                    config_item = AIStorage.get_instance().get_user_config().get_config_item(key)
                    old_value = AIStorage.get_instance().get_user_config().get_value(key)
                    
                    if config_item is not None:
                        value = await session.prompt_async(f"{key} : {config_item.desc} \nCurrent : {old_value}\nPlease input new value:",style=shell_style)
                        AIStorage.get_instance().get_user_config().set_value(key,value)
                        await AIStorage.get_instance().get_user_config().save_to_user_config()
                        show_text = FormattedText([("class:title", f"set {key} to {value} success!")])
                
                return show_text
            case 'connect':
                show_text = FormattedText([("class:title", "args error, /connect $target telegram | email")])
                if len(args) < 1:
                    return show_text
                tunnel_target = args[0]
                if len(args) < 2:
                    tunnel_type = "telegram"
                else:
                    tunnel_type = args[1]

                tunnel_config = await self.get_tunnel_config_from_input(tunnel_target,tunnel_type)
                if tunnel_config:
                    if await AgentTunnel.load_tunnel_from_config(tunnel_config):
                        # append
                        await self.append_tunnel_config(tunnel_config)
                        show_text = FormattedText([("class:title", f"connect to {tunnel_target} success!")])

                return show_text
            case 'open':
                if len(args) >= 1:
                    target_id = args[0]
                if len(args) >= 2:
                    topic = args[1]

                self.current_target = target_id
                self.current_topic = topic
                show_text = FormattedText([("class:title", f"current session switch to {topic}@{target_id}")])
                AIStorage.get_instance().get_user_config().set_value("shell.current",f"{self.current_topic}@{self.current_target}")
                await AIStorage.get_instance().get_user_config().save_to_user_config()
                return show_text
            case 'login':
                if len(args) >= 1:
                    self.username = args[0]
                AIBus().get_default_bus().register_message_handler(self.username,self._user_process_msg)
                
                return self.username + " login success!"    
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
                    db_path = AgentManager.get_instance().db_path
                else:
                    db_path = WorkflowManager.get_instance().db_file
                chatsession:AIChatSession = AIChatSession.get_session(self.current_target,f"{self.username}#{self.current_topic}",db_path,False)
                if chatsession is not None:
                    msgs = chatsession.read_history(num,offset)
                    format_texts = []
                    for msg in msgs:
                        format_texts.append(("class:content",f"{msg.sender} >>> {msg.body}"))
                        format_texts.append(("",f"\n-------------------\n"))
                    return FormattedText(format_texts)
                return FormattedText([("class:title", f"chatsession not found")])
            case 'exit':
                os._exit(0)
            case 'help':
                return FormattedText([("class:title", f"help~~~")])


##########################################################################################################################    
history = FileHistory('aios_shell_history.txt')
session = PromptSession(history=history) 

def parse_function_call(func_string):
    if len(func_string) > 2:
        if func_string[0] == '/' and func_string[1] != '/':
            str_list = shlex.split(func_string[1:])
            func_name = str_list[0]
            params = str_list[1:]
            return func_name, params
    else:
        return None
    
async def try_get_input(desc:str,check_func:callable = None) -> str:
    user_input = await session.prompt_async(f"{desc} \nType /exit to abort. \nPlease input:",style=shell_style)
    err_str = ""
    if check_func is None:
        if len(user_input) > 0:
            if user_input != "/exit":
                return user_input
            else:
                return None
        
    else:
        is_ok,err_str = check_func(user_input)
        if is_ok:
            return user_input
    
    error_text = FormattedText([("class:error", err_str)])    
    print_formatted_text(error_text,style=shell_style)
    return await try_get_input(desc,check_func)

async def get_user_config_from_input(check_result:dict) -> bool:
    for key,item in check_result.items():
        user_input = await try_get_input(f"System config {key} ({item.desc}) not define!")
        if len(user_input) > 0:
            AIStorage.get_instance().get_user_config().set_value(key,user_input)

    await AIStorage.get_instance().get_user_config().save_to_user_config()
    return True

async def main_daemon_loop(shell:AIOS_Shell):
    while shell.is_working:
        await asyncio.sleep(1)

    return 0

def print_welcome_screen():
    print("\033[1;31m")  
    logo = """
\t   _______                    ____________________   __
\t   __  __ \______________________  __ \__    |__  | / /
\t   _  / / /__  __ \  _ \_  __ \_  / / /_  /| |_   |/ / 
\t   / /_/ /__  /_/ /  __/  / / /  /_/ /_  ___ |  /|  /  
\t   \____/ _  .___/\___//_/ /_//_____/ /_/  |_/_/ |_/   
\t           /_/                                          

    """
    print(logo)
    print("\033[0m")  

    print("\033[1;32m \t\tWelcome to OpenDAN - Your Personal AI OS\033[0m\n")  

    introduce = """
\tThe core goal of version 0.5.1 is to turn the concept of AIOS into code and get it up and running as quickly as possible. 
\tAfter three weeks of development, our plans have undergone some changes based on the actual progress of the system. 
\tUnder the guidance of this goal, some components do not need to be fully implemented. Furthermore, 
\tbased on the actual development experience from several demo Intelligent Applications, 
\twe intend to strengthen some components. This document will explain these changes and provide an update 
\ton the current development progress of MVP(0.5.1,0.5.2)

""" 
    print(introduce)

    print(f"\033[1;34m \t\tVersion: {AIOS_Version}\n\033")  
    print("\033[1;33m \tOpenDAN is an open-source project, let's define the future of Humans and AI together.\033[0m")  
    print("\033[1;33m \tGithub\t: https://github.com/fiatrete/OpenDAN-Personal-AI-OS\033[0m")  
    print("\033[1;33m \tWebsite\t: https://www.opendan.ai\033[0m")
    print("\n\n")


async def main():
    print_welcome_screen()
    print("Booting...")
    logging.basicConfig(filename="aios_shell.log",filemode="w",encoding='utf-8',force=True,
                        level=logging.INFO,
                        format='[%(asctime)s]%(name)s[%(levelname)s]: %(message)s')
    
    if os.path.isdir(f"{directory}/../../../rootfs"):
        AIStorage.get_instance().is_dev_mode = True
    else:
        AIStorage.get_instance().is_dev_mode = False    

    is_daemon = False
    if os.name != 'nt':
        if os.getppid() == 1:
            is_daemon = True

    shell = AIOS_Shell("user")   
    shell.declare_all_user_config() 
    await AIStorage.get_instance().initial()
    check_result = AIStorage.get_instance().get_user_config().check_config()
    if check_result is not None:
        if is_daemon:
            logger.error(check_result)
            return 1
        else:
            #Remind users to enter necessary configurations.
            if await get_user_config_from_input(check_result) is False:
                return 1
    
    init_result = await shell.initial()
    if init_result is False:
        if is_daemon:
            logger.error("aios shell initial failed!")
            return 1
        else:
            print("aios shell initial failed!")

    print(f"aios shell {shell.get_version()} ready.")
    if is_daemon:
        return await main_daemon_loop(shell)

    proxy.apply_storage()

    #TODO: read last input config
    completer = WordCompleter(['/send $target $msg $topic', 
                               '/open $target $topic', 
                               '/history $num $offset',
                               '/login $username',
                               '/connect $target',
                               '/set_config $key',
                               '/list_config',
                               '/show',
                               '/exit', 
                               '/help'], ignore_case=True)

    current = AIStorage.get_instance().get_user_config().get_value("shell.current")
    current = current.split("@")
    shell.current_target = current[1]
    shell.current_topic = current[0]

    await asyncio.sleep(0.2) 
    while True:
        user_input = await session.prompt_async(f"{shell.username}<->{shell.current_topic}@{shell.current_target}$ ",completer=completer,style=shell_style)
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

