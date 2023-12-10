from ast import Dict
from datetime import timedelta
from typing import List

from ..frame.compute_kernel import ComputeKernel
from ..proto.ai_function import SimpleAIOperation

from .chatsession import *

class AgentMemory:
    def __init__(self,agent_id:str,db_path:str) -> None:
        self.agent_id:str= agent_id
        self.chat_db:str = db_path
        self.model_name:str = "gp4-1106-preview"
        self.threshold_hours = 72

        self.actions = {}
        self.init_actions()

    def init_actions(self) -> Dict:
        chatlog_append_op = SimpleAIOperation("chatlog_append","Append request & reply message to chatlog. No params",self.action_chatlog_append)
        self.actions[chatlog_append_op.get_name()] = chatlog_append_op

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
        # 必定加载n条(n>=2),期望加载m条
        # m条里的信息逐步添加，知道距离现在的时间未72小时以上，且消耗了足够的Token

        messages_n = chatsession.read_history(n) # read
        if len(messages_n) >= n:
            messages_m = chatsession.read_history(m,n)
        else:
            messages_m = []

        histroy_str = ""
        read_count = 0
        for msg in messages_n:
            dt = datetime.datetime.fromtimestamp(float(msg.create_time))
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

        now = datetime.datetime.now()
        for msg in messages_m:
            dt = datetime.datetime.fromtimestamp(float(msg.create_time))
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
    
    def get_actions(self) -> Dict:
        return self.actions
    
    async def get_log_summary(self,msg:AgentMsg) -> str:
        return None
    
    
