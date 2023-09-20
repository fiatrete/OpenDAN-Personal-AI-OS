from typing import Optional

from asyncio import Queue
import asyncio
import logging
import uuid
import time
import json
import shlex

from .agent_message import AgentMsg, AgentMsgStatus, AgentMsgType
from .chatsession import AIChatSession
from .compute_task import ComputeTaskResult
from .ai_function import AIFunction
from .environment import Environment

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
        self.agent_id:str = None
        self.template_id:str = None
        self.fullname:str = None
        self.powerby = None  
        self.enable = True

        self.chat_db = None
        self.unread_msg = Queue() # msg from other agent
        self.owner_env : Environment = None
        self.owenr_bus = None
        
    @classmethod
    def create_from_templete(cls,templete:AIAgentTemplete, fullname:str):
        # Agent just inherit from templete on craete,if template changed,agent will not change
        result_agent = AIAgent()
        result_agent.llm_model_name = templete.llm_model_name
        result_agent.max_token_size = templete.max_token_size
        result_agent.template_id = templete.template_id
        result_agent.agent_id = "agent#" + uuid.uuid4().hex
        result_agent.fullname = fullname
        result_agent.powerby = templete.author
        result_agent.prompt = templete.prompt
        return result_agent
    
    def load_from_config(self,config:dict) -> bool:
        if config.get("instance_id") is None:
            logger.error("agent instance_id is None!")
            return False
        self.agent_id = config["instance_id"]

        if config.get("fullname") is None:
            logger.error(f"agent {self.agent_id} fullname is None!")
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
    
    def _get_inner_functions(self) -> dict:
        if self.owner_env is None:
            return None
        
        all_inner_function = self.owner_env.get_all_ai_functions()
        if all_inner_function is None:
            return None
        
        result_func = []
        for inner_func in all_inner_function:
            this_func = {}
            this_func["name"] = inner_func.get_name()
            this_func["description"] = inner_func.get_description()
            this_func["parameters"] = inner_func.get_parameters()
            result_func.append(this_func)

        return result_func 

    async def _execute_func(self,inenr_func_call_node:dict,prompt:AgentPrompt,org_msg:AgentMsg) -> str:
        from .compute_kernel import ComputeKernel

        func_name = inenr_func_call_node.get("name")
        arguments = json.loads(inenr_func_call_node.get("arguments"))

        func_node : AIFunction = self.owner_env.get_ai_function(func_name)
        if func_node is None:
            return "execute failed,function not found"
        
        ineternal_call_record = AgentMsg.create_internal_call_msg(func_name,arguments,org_msg.get_msg_id(),org_msg.target)

        result_str:str = await func_node.execute(**arguments)
        
        inner_functions = self._get_inner_functions()
        prompt.messages.append({"role":"function","content":result_str,"name":func_name})
        task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,self.llm_model_name,self.max_token_size,inner_functions)
        
        ineternal_call_record.result_str = task_result.result_str
        ineternal_call_record.done_time = time.time()
        org_msg.inner_call_chain.append(ineternal_call_record)

        inner_func_call_node = task_result.result_message.get("function_call")
        if inner_func_call_node:
            return await self._execute_func(inner_func_call_node,prompt,org_msg)      
        else:
            return task_result.result_str

    async def _process_msg(self,msg:AgentMsg) -> AgentMsg:
            from .compute_kernel import ComputeKernel

            session_topic = msg.get_sender() + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.chat_db)
            if msg.mentions is not None:
                if not self.agent_id in msg.mentions:
                    chatsession.append(msg)
                    logger.info(f"agent {self.agent_id} recv a group chat message from {msg.sender},but is not mentioned,ignore!")
                    return None
            
            prompt = AgentPrompt()
            prompt.append(self.prompt)
            # prompt.append(self._get_knowlege_prompt(the_role.get_name()))
            prompt.append(await self._get_prompt_from_session(chatsession)) # chat context
            
            msg_prompt = AgentPrompt()
            msg_prompt.messages = [{"role":"user","content":msg.body}]
            prompt.append(msg_prompt)

            inner_functions = self._get_inner_functions()

            task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,self.llm_model_name,self.max_token_size,inner_functions)
            final_result = task_result.result_str

            inner_func_call_node = task_result.result_message.get("function_call")
            if inner_func_call_node:
                #TODO to save more token ,can i use msg_prompt?
                final_result = await self._execute_func(inner_func_call_node,prompt,msg)
            
            result_type : str = self._get_llm_result_type(final_result)
            is_ignore = False

            match result_type:
                case "ignore":
                    is_ignore = True
                    
            if is_ignore is not True:
                resp_msg = msg.create_resp_msg(final_result)
                chatsession.append(msg)
                chatsession.append(resp_msg)
                
                return resp_msg
            
            return None
        
    def get_id(self) -> str:
        return self.agent_id
    
    def get_fullname(self) -> str:
        return self.fullname

    def get_template_id(self) -> str:
        return self.template_id

    def get_llm_model_name(self) -> str:
        return self.llm_model_name
    
    def get_max_token_size(self) -> int:
        return self.max_token_size
    
    async def _get_prompt_from_session(self,chatsession:AIChatSession,is_groupchat=False) -> AgentPrompt:
        # TODO: get prompt from group chat is different from single chat
        messages = chatsession.read_history() # read 
        result_prompt = AgentPrompt()
        for msg in reversed(messages):
            if msg.sender == self.agent_id:
                result_prompt.messages.append({"role":"assistant","content":msg.body})
            else:
                result_prompt.messages.append({"role":"user","content":msg.body})
        return result_prompt

