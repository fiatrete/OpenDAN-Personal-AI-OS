from typing import Optional

from asyncio import Queue
import asyncio
import logging
import uuid
import time

from .agent_message import AgentMsg
from .chatsession import AIChatSession

logger = logging.getLogger(__name__)


class AgentPrompt:
    def __init__(self) -> None:
        self.messages = []

    def as_str(self)->str:
        result_str = "" 
        if self.messages:
            for msg in self.messages:
                result_str += msg.get("role") + ":" + msg.get("content") + "\n"

        return result_str
    
    def append(self,prompt):
        if prompt is None:
            return
        
        self.messages.extend(prompt.messages)

    def load_from_config(self,config:list) -> bool:
        if isinstance(config,list) is not True:
            logger.error("prompt is not list!")
            return False
        
        self.messages = config
        return True


class AIAgentTemplete:
    def __init__(self) -> None:
        self.llm_model_name:str = "gpt-4-0613"
        self.max_token_size:int = 0
        self.template_id:str = None
        self.introduce:str = None
        self.author:str = None
        self.prompt:AgentPrompt = None

    def load_from_config(self,config:dict) -> bool:
        if config.get("llm_model_name") is not None:
            self.llm_model_name = config["llm_model_name"]
        if config.get("max_token_size") is not None:
            self.max_token_size = config["max_token_size"]
        if config.get("template_id") is not None:
            self.template_id = config["template_id"]
        if config.get("prompt") is not None:
            self.prompt = AgentPrompt()
            if self.prompt.load_from_config(config["prompt"]) is False:
                logger.error("load prompt from config failed!")
                return False
        
        return True
    

class AIAgent:
    def __init__(self) -> None:
        self.prompt:AgentPrompt = None
        self.llm_model_name:str = None
        self.max_token_size:int = 3600
        self.instance_id:str = None
        self.template_id:str = None
        self.fullname:str = None
        self.powerby = None  
        self.enable = True

        self.chat_db = None
        self.unread_msg = Queue() # msg from other agent
        
    @classmethod
    def create_from_templete(cls,templete:AIAgentTemplete, fullname:str):
        # Agent just inherit from templete on craete,if template changed,agent will not change
        result_agent = AIAgent()
        result_agent.llm_model_name = templete.llm_model_name
        result_agent.max_token_size = templete.max_token_size
        result_agent.template_id = templete.template_id
        result_agent.instance_id = "agent#" + uuid.uuid4().hex
        result_agent.fullname = fullname
        result_agent.powerby = templete.author
        result_agent.prompt = templete.prompt
        return result_agent
    
    def load_from_config(self,config:dict) -> bool:
        if config.get("instance_id") is None:
            logger.error("agent instance_id is None!")
            return False
        self.instance_id = config["instance_id"]

        if config.get("fullname") is None:
            logger.error(f"agent {self.instance_id} fullname is None!")
            return False
        self.fullname = config["fullname"]

        if config.get("prompt") is not None:
            self.prompt = AgentPrompt()
            self.prompt.load_from_config(config["prompt"])

        if config.get("powerby") is not None:
            self.powerby = config["powerby"]
        if config.get("template_id") is not None:
            self.template_id = config["template_id"]
        if config.get("llm_model_name") is not None:
            self.llm_model_name = config["llm_model_name"]
        if config.get("max_token_size") is not None:
            self.max_token_size = config["max_token_size"]

        return True


    def _get_llm_result_type(self,result:str) -> str:
        if result == "ignore":
            return "ignore"
        
        return "text"

    async def _process_msg(self,msg:AgentMsg) -> AgentMsg:
            from .compute_kernel import ComputeKernel
            session_topic = msg.get_sender() + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.instance_id,session_topic,self.chat_db)
            prompt = AgentPrompt()
            prompt.append(self.prompt)
 
            # prompt.append(self._get_function_prompt(the_role.get_name()))
            # prompt.append(self._get_knowlege_prompt(the_role.get_name()))
            prompt.append(await self._get_prompt_from_session(chatsession)) # chat context
            
            msg_prompt = AgentPrompt()
            msg_prompt.messages = [{"role":"user","content":msg.body}]
            prompt.append(msg_prompt)
    
            result = await ComputeKernel().do_llm_completion(prompt,self.llm_model_name,self.max_token_size)
            final_result = result
            result_type : str = self._get_llm_result_type(result)
            is_ignore = False

            match result_type:
                # case "function":
                #    callchain:CallChain = self._parse_function_call_chain(result)
                #    resp = await callchain.exec()
                #    if callchain.have_result():
                #        # generator proc resp prompt with WAITING state
                #        proc_resp_prompt:AgentPrompt = self._get_resp_prompt(resp,msg,the_role,prompt,chatsession)
                #        final_result = await ComputeKernel().do_llm_completion(proc_resp_prompt,the_role.agent.get_llm_model_name(),the_role.agent.get_max_token_size())
                #        return final_result

                
                # case "send_message":
                #    # send message to other / sub workflow
                #    next_msg:AgentMsg = self._parse_to_msg(result)
                #    if next_msg is not None:
                #        # TODO: Next Target can be another role in workflow
                #        next_workflow:Workflow = self.get_workflow(next_msg.get_target())
                #        inner_chat_session = the_role.agent.get_chat_session(next_msg.get_target(),next_msg.get_session_id())

                #        inner_chat_session.append_post(next_msg)
                #        resp = await next_workflow.send_msg(next_msg)
                #        inner_chat_session.append_recv(resp)
                #        # generator proc resp prompt with WAITING state
                #        proc_resp_prompt:AgentPrompt = self._get_resp_prompt(resp,msg,the_role,prompt,chatsession)
                #        final_result = await ComputeKernel().do_llm_completion(proc_resp_prompt,the_role.agent.get_llm_model_name(),the_role.agent.get_max_token_size())
                        
                #        return final_result
                    
                #case "post_message":
                #    # post message to other / sub workflow
                #    next_msg:AgentMsg = self._parse_to_msg(result)
                #    if next_msg is not None:
                #        next_workflow:Workflow = self.get_workflow(next_msg.get_target())
                #        inner_chat_session = the_role.agent.get_chat_session(next_msg.get_target(),next_msg.get_session_id())
                #        inner_chat_session.append_post(next_msg)
                #        next_workflow.post_msg(next_msg)

                case "ignore":
                    is_ignore = True
                    
            if is_ignore is not True:
                # TODO : how to get inner chat session?
                resp_msg = AgentMsg()
                resp_msg.set(self.instance_id,msg.sender,final_result)
                resp_msg.topic = msg.topic

                if chatsession is not None:
                    chatsession.append_recv(msg)
                    chatsession.append_post(resp_msg)
                
                return resp_msg
            
            return None
        
    def get_id(self) -> str:
        return self.instance_id
    
    def get_fullname(self) -> str:
        return self.fullname

    def get_template_id(self) -> str:
        return self.template_id

    def get_llm_model_name(self) -> str:
        return self.llm_model_name
    
    def get_max_token_size(self) -> int:
        return self.max_token_size
    
    async def _get_prompt_from_session(self,chatsession:AIChatSession) -> AgentPrompt:
        messages = chatsession.read_history() # read last 10 message
        result_prompt = AgentPrompt()
        for msg in reversed(messages):
            if msg.target == chatsession.owner_id:
                result_prompt.messages.append({"role":"user","content":f"{msg.sender}:{msg.body}"})
            if msg.sender == chatsession.owner_id:
                result_prompt.messages.append({"role":"assistant","content":msg.body})
        
        return result_prompt

