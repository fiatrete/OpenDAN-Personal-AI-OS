# pylint:disable=E0402
from datetime import datetime,timedelta
from typing import Dict

from ..frame.compute_kernel import ComputeKernel
from ..proto.ai_function import SimpleAIAction
from ..proto.agent_msg import AgentMsg, AgentMsgType

from .llm_context import GlobaToolsLibrary
from .chatsession import AIChatSession

import logging

logger = logging.getLogger(__name__)

class AgentMemory:
    def __init__(self,agent_id:str,db_path:str) -> None:
        self.agent_id:str= agent_id
        self.chat_db:str = db_path
        self.model_name:str = "gp4-1106-preview"
        self.threshold_hours = 72

    @classmethod
    def register_actions(cls):
        async def action_chatlog_append(parms:Dict):
            memory = parms.get("_memory")
            if memory:
                return await memory.action_chatlog_append(parms)
            
        chatlog_append_action = SimpleAIAction("chatlog_append","Append request & reply message to chatlog. No params",action_chatlog_append)
        GlobaToolsLibrary.get_instance().register_tool_function(chatlog_append_action,"agent.memory.chatlog.append")
        

    def get_session_from_msg(self,msg:AgentMsg) -> AIChatSession:
        if msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
            session_topic = msg.target + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.chat_db)
        else:
            session_topic = msg.get_sender() + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.chat_db)
        return chatsession

    async def load_chatlogs(self,msg:AgentMsg,n:int=6,m:int=64,token_limit=800)->str:
        chatsession = self.get_session_from_msg(msg)
        # Must load n (n> = 2), and hope to load the M
        # The information in the # M is gradually added, knowing that it is less than 72 hours from the current time, and consumes enough tokens

        messages_n = chatsession.read_history(n) # read
        if len(messages_n) >= n:
            messages_m = chatsession.read_history(m,n)
        else:
            messages_m = []

        histroy_str = ""
        read_count = 0
        for msg in messages_n:
            dt = datetime.fromtimestamp(float(msg.create_time))
            formatted_time = dt.strftime('%y-%m-%d %H:%M:%S')
            record_str = f"{msg.sender},[{formatted_time}]\n{msg.body}\n"
            token_limit -= ComputeKernel.llm_num_tokens_from_text(record_str,self.model_name)
            if token_limit <= 32:
                break
            read_count += 1
            histroy_str = record_str + histroy_str

        if len(messages_n) > 2:
            if read_count < 3:
                logging.warning(f"read history {read_count} < 3, will not load more")

        now = datetime.now()
        for msg in messages_m:
            dt = datetime.fromtimestamp(float(msg.create_time))
            time_diff = now - dt
            if time_diff > timedelta(hours=self.threshold_hours):
                break

            formatted_time = dt.strftime('%y-%m-%d %H:%M:%S')
            record_str = f"{msg.sender},[{formatted_time}]\n{msg.body}\n"
            token_limit -= ComputeKernel.llm_num_tokens_from_text(record_str,self.model_name)
            if token_limit <= 32:
                break
            read_count += 1
            histroy_str = record_str + histroy_str

        return histroy_str 
    
    async def action_chatlog_append(self,params:Dict) -> str:
        # 使用params可以得到: LLM Process的输入，LLM Result,基于LLM Result构造的参数，当前actionItem
        input_msg:AgentMsg = params.get("input").get("msg")
        llm_result = params.get("llm_result")
        chatsession = self.get_session_from_msg(input_msg)
        resp_msg = params.get("resp_msg")
        if resp_msg:
            tags =  llm_result.raw_result.get("tags")
            chatsession.append(input_msg,tags)
            chatsession.append(resp_msg,tags)
    
        return "OK"
    
    async def get_contact_summary(self,contact_id:str) -> str:
        if contact_id is None:
            return None
        
        if contact_id == "lzc":
            return "lzc is your master. Male, 40 years old, Mother tongue is Chinese, senior software engineer."
        return None
    
    async def update_contact_summary(self,contact_id:str,summary:str) -> str:
        return "OK"
    
    async def get_sth_summary(self,sth_id:str) -> str:
        return None
    
    async def update_sth_summary(self,sth_id:str,summary:str) -> str:
        return None
    
    async def get_log_summary(self,msg:AgentMsg) -> str:
        return None
    

    
    
