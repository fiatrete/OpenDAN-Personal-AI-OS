from typing import Optional
from enum import Enum
from asyncio import Queue
import asyncio
import logging
import uuid
import time


logger = logging.getLogger(__name__)


class AgentMsgState(Enum):
    RESPONSED = 0
    INIT = 1
    SENDING = 2
    PROCESSING = 3
    ERROR = 4

class AgentMsg:
    def __init__(self) -> None:
        self.create_time = 0
        self.sender:str = None
        self.target:str = None
        self.body:str = None
        self.state = AgentMsgState.INIT

        self.resp_msg = None

    def set(self,sender:str,target:str,body:str) -> None:
        self.sender = sender
        self.target = target
        self.body = body
        self.create_time = time.time()

    def get_msg_id(self) -> str:
        pass

    def get_sender(self) -> str:
        return self.sender

    def get_target(self) -> str:
        return self.target

    # return workflow_name, role_name, session_id
    def parser_target(self,target:str) -> None:
        pass

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
        self.messages.extend(prompt.messages)

    def load_from_config(self,config:list) -> bool:
        if isinstance(config,list) is not True:
            logger.error("prompt is not list!")
            return False
        
        self.messages = config
        return True

# chat session store the chat history between owner and agent
# chat session might be large, so can read / write at stream mode.
class AIChatSession:
    def __init__(self,owner_id) -> None:
        self.owner_id = owner_id

    def get_owner_id(self) -> str:
        return self.owner_id

    def append_post(self,msg:AgentMsg) -> None:
        """append msg to session, msg is post from session (owner => msg.target)"""
        pass

    def append_recv(self,msg:AgentMsg) -> None:
        """append msg to session, msg is recv from msg'sender (msg.sender => owner)"""
        pass    

    def attach_event_handler(self,handler) -> None:
        """chat session changed event handler"""
        pass

    #TODO : add iterator interface for read chat history 

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
        self.max_token_size:int = 0
        self.instance_id:str = None
        self.template_id:str = None
        self.fullname:str = None
        self.powerby = None  
        self.enable = True

        self.chat_sessions = {} 
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

    def post_msg(self,msg:AgentMsg) -> None:
        # TODO: drop same msg already processed
        msg.state = AgentMsgState.SENDING
        self.unread_msg.put_nowait(msg)

    def start(self) -> None:
        async def _process_msg_loop():
            while True:
                msg = await self.unread_msg.get()
                if msg is None:
                    continue
                msg.state = AgentMsgState.PROCESSING
                resp_msg = await self._process_msg(msg)
                if resp_msg is None:
                    msg.state = AgentMsgState.ERROR
                    continue
                else:
                    msg.state = AgentMsgState.RESPONSED
                    msg.resp_msg = resp_msg
        
        asyncio.create_task(_process_msg_loop())

    def _get_llm_result_type(self,result:str) -> str:
        if result == "ignore":
            return "ignore"
        
        return "text"

    async def _process_msg(self,msg:AgentMsg) -> AgentMsg:
            from .compute_kernel import ComputeKernel

            prompt = AgentPrompt()
            prompt.append(self.prompt)
            msg_prompt = AgentPrompt()
            msg_prompt.messages = [{"role":msg.sender,"content":msg.body}]
            prompt.append(msg_prompt)
            # prompt.append(self._get_function_prompt(the_role.get_name()))
            # prompt.append(self._get_knowlege_prompt(the_role.get_name()))
            # prompt.append(await self._get_prompt_from_session(chatsession,the_role.get_name())) # chat context

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
                chatsession = self.get_chat_session(msg.sender)
                resp_msg = AgentMsg()
                resp_msg.set(self.instance_id,msg.sender,final_result)
                if chatsession is not None:
                    chatsession.append_recv(msg)
                    chatsession.append_post(final_result)
                
                return resp_msg
            
            return None
        
    def get_id(self) -> str:
        return self.instance_id
    
    def get_fullname(self) -> str:
        return self.fullname

    def get_template_id(self) -> str:
        return self.template_id

    def get_chat_session_for_msg(self,msg:AgentMsg) -> AIChatSession:
        pass

    def get_chat_session(self,remote:str,topic_name:str=None) -> AIChatSession:
        if topic_name is None:
            topic_name = "_"

        result_session = self.chat_sessions.get(topic_name + "@" + remote)
        if result_session is not None:
            return result_session    
        
        result_session = AIChatSession(self)
        self.chat_sessions[topic_name + "@" + remote] = result_session
        return result_session


    def get_llm_model_name(self) -> str:
        return self.llm_model_name
    
    def get_max_token_size(self) -> int:
        return self.max_token_size

