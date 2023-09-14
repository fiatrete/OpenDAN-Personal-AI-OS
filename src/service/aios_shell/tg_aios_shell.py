
import asyncio
import sys
import os
import logging
import re

from typing import Any, Optional, TypeVar, Tuple, Sequence
import argparse

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters


directory = os.path.dirname(__file__)
sys.path.append(directory + '/../../')
from aios_kernel import Workflow,AIAgent,AgentMsg,AgentMsgStatus,ComputeKernel,OpenAI_ComputeNode,AIBus,AIChatSession

sys.path.append(directory + '/../../component/')
from agent_manager import AgentManager
from workflow_manager import WorkflowManager
from aios_kernel import CalenderEnvironment,Environment

import logging

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

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
        cal_env = CalenderEnvironment("calender")
        cal_env.start()
        Environment.set_env_by_id("calender",cal_env)
        
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
        
            
                return resp
            case 'open':
                if len(args) >= 1:
                    target_id = args[0]
                if len(args) >= 2:
                    topic = args[1]

                self.current_target = target_id
                self.current_topic = topic
                show_text = f"current session switch to {topic}@{target_id}"
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
                    result_str = ""
                    for msg in reversed(msgs):
                        result_str += f"{msg.sender} >>> {msg.body}"
                        result_str += f"\n-------------------\n"
                    return result_str
                return f"chatsession not found"
            case 'help':
                return "help info "

shell:AIOS_Shell = None

async def _init_shell():
    global shell
    if shell is None:
        shell = AIOS_Shell("user")
        await shell.initial()
    return 

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await _init_shell()
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _init_shell()
    cmd_msg = update.message.text[1:]
    logger.info("command:" + cmd_msg)
    func_call = parse_function_call(cmd_msg)
    if func_call:
        shell.username = update.effective_user
        show_text = await shell.call_func(func_call[0], func_call[1])
        await update.message.reply_text(show_text)
    else:
        await update.message.reply_text("command not found!")

async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _init_shell()
    shell.username = update.effective_user
    resp = await shell.send_msg(update.message.text,shell.current_target,shell.current_topic,shell.username)
    await update.message.reply_text(resp)




def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    tg_robot_token = os.getenv("TG_ROBOT_TOKEN")
    if tg_robot_token is None:
        print("TG_ROBOT_TOKEN not found!")
        tg_robot_token = input("input your telegram robot token:")


    if tg_robot_token is None:
        return

    application = Application.builder().token(tg_robot_token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", on_command))
    application.add_handler(CommandHandler("send", on_command))
    application.add_handler(CommandHandler("open", on_command))
    application.add_handler(CommandHandler("history", on_command))

    # on non command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()