
import logging
import asyncio
import json
from asyncio import Queue
from typing import Optional,Tuple
from abc import ABC, abstractmethod

from .environment import Environment,EnvironmentEvent
from .agent_message import AgentMsg,AgentMsgState
from .agent import AgentPrompt,AgentMsg
from .chatsession import AIChatSession
from .role import AIRole,AIRoleGroup
from .ai_function import CallChain
from .compute_kernel import ComputeKernel
from .bus import AIBus

logger = logging.getLogger(__name__)

class MessageFilter:
    def __init__(self) -> None:
        self.filters = {}

    def select(self,msg:AgentMsg) -> str:
        star_target = self.filters.get("*")
        if star_target is not None:
            return star_target

        # TODO: add more filter
        return None
            
    def load_from_config(self,config:dict) -> bool:
        self.filters = config
        return True


class LLMResult:
    def __init__(self) -> None:
        self.state : str = "ignore"
        self.resp : str = ""
        self.post_msgs = []
        self.send_msgs = []
        self.calls = []
        self.post_calls = []


class Workflow:
    def __init__(self) -> None:
        self.workflow_name : str = None
        self.workflow_id : str = None
        self.rule_prompt : AgentPrompt = None
        self.workflow_config = None
        self.role_group : dict = None
        self.input_filter : MessageFilter= None
        self.connected_environment = {}
        self.sub_workflows = {}
        self.owner_workflow = None
        self.db_file = None

        self.is_start = False
        self.msg_queue = Queue()

    def get_bus(self) -> AIBus:
        return AIBus.get_default_bus()

    def set_owner(self,owner):
        self.owner_workflow = owner

    def load_from_config(self,config:dict) -> bool:
        if config is None:
            return False
        
        if config.get("name") is None: 
            logger.error("workflow config must have name")
            return False
        self.workflow_name = config.get("name")
        if self.owner_workflow is None:
            self.workflow_id = self.workflow_name
        else:
            self.workflow_id = self.owner_workflow.workflow_id + "." + self.workflow_name
            self.db_file = self.owner_workflow.db_file

        if config.get("prompt") is not None:
            self.rule_prompt = AgentPrompt()
            if self.rule_prompt.load_from_config(config.get("prompt")) is False:
                logger.error("Workflow load prompt failed")
                return False
            
        if config.get("roles") is None:
            logger.error("workflow config must have roles")
            return False
        self.role_group = AIRoleGroup()
        self.role_group.owner_name = self.workflow_id
        if self.role_group.load_from_config(config.get("roles")) is False:
            logger.error("Workflow load role_group failed")
            return False

        if config.get("filter") is not None:
            self.input_filter = MessageFilter()
            if self.input_filter.load_from_config(config.get("filter")) is False:
                logger.error("Workflow load input_filter failed")
                return False
            
        sub_workflows = config.get("sub_workflows")
        if sub_workflows is not None:
            if self._load_sub_workflows(sub_workflows) is False:
                logger.error("Workflow load sub workflows failed")
                return False
            
        #TODO: load env
        
        return True

    def _load_sub_workflows(self,config:dict) -> bool:
        for k,v in config.items():
            sub_workflow = Workflow()
            sub_workflow.set_owner(self)

            if sub_workflow.load_from_config(v) is False:
                logger.error(f"load sub workflow {k} failed!")
                return False
            self.sub_workflows[k] = sub_workflow
        return True
    
    def _parse_msg_target(self,s:str)->list[str]:
        return s.split(".")

    async def _forword_msg(self,inner_obj_id,msg):
        i : int = 1
        current_workflow = self
        while i < len(inner_obj_id):
            if i == len(inner_obj_id) - 1:
                the_role : AIRole = current_workflow.role_group.get(inner_obj_id[i])
                if the_role is not None:
                    return await current_workflow.role_process_msg(msg,the_role)
                sub_workflow = current_workflow.sub_workflows.get(inner_obj_id[i])
                if sub_workflow is not None:
                    return await sub_workflow.process_msg(msg)
                logger.error(f"{msg.target} not found! forword message failed!")
                return None
            else:
                current_workflow = current_workflow.sub_workflows.get(inner_obj_id[i])
                if current_workflow is None:
                    logger.error(f"sub workflow {inner_obj_id[i]} not found!")
                    return None
            
            i += 1
        
        logger.error(f"{msg.target} not found! forword message failed!")
        return None
        

    async def _process_msg(self,msg:AgentMsg):
        # workflow can be a message handler, but never be a message sender
        # all message forword to roles or sub workflow
        # workflow no chatsession record, but role have
        
        final_result = None

        targets = self._parse_msg_target(msg.target)
        if len(targets) > 1:
            return await self._forword_msg(targets,msg)
            
        if self.input_filter is not None:
            select_role_id = self.input_filter.select(msg)
            if select_role_id is not None: 
                select_role = self.role_group.get(select_role_id)
                if select_role is None:
                    logger.error(f"input_filter return invalid role id:{select_role_id}, role not found in role_group")
                    return None

                result = await self.role_process_msg(msg,select_role)
                if result is None:
                    logger.error(f"_process_msg return None for :{msg}")
                    return

                final_result = result
            else:
                logger.error(f"input_filter return None for :{msg}")
                return
                
        else:
            # no input filter, we would process all message, slowly,not suggest to use 
            results = {}
            final_result:AgentMsg  = None 
            for this_role in self.role_group.roles.values():
                # TODO : we would do this in parallel
                a_result = await self.role_process_msg(msg,this_role)
                results[this_role.get_name()] = a_result
                final_result = a_result
        
        return final_result

    @classmethod
    def prase_llm_result(cls,llm_result_str:str)->LLMResult:
        r = LLMResult()
        if llm_result_str is None:
            r.state = "ignore"
            return r
        if llm_result_str == "ignore":
            r.state = "ignore"
            return r
        
        lines = llm_result_str.splitlines()
        is_need_wait = False
        for line in lines:
            func_call = AgentMsg.parse_function_call(line)
            if func_call:
                func_args = func_call[1]
                match func_call[0]:
                    case "sendmsg":# sendmsg($target_id,$msg_content)
                        if len(func_args) != 2:
                            logger.error(f"parse sendmsg failed! {func_call}")
                            continue
                        new_msg = AgentMsg()
                        target_id = func_args[0]
                        msg_content = func_args[1]
                        new_msg.set("_",target_id,msg_content)
    
                        r.send_msgs.append(new_msg)
                        is_need_wait = True
                        continue
                    case "postmsg":# postmsg($target_id,$msg_content)
                        if len(func_args) != 2:
                            logger.error(f"parse postmsg failed! {func_call}")
                            continue
                        new_msg = AgentMsg()
                        target_id = func_args[0]
                        msg_content = func_args[1]
                        new_msg.set("_",target_id,msg_content)
                        r.post_msgs.append(new_msg)
                        continue
                    case "call":# call($func_name,$args_str)
                        r.calls.append(func_call)
                        is_need_wait = True
                        continue 
                    case "post_call": # post_call($func_name,$args_str)
                        r.post_calls.append(func_call)
                        continue
                
                r.resp += line + "\n"
            else:
                r.resp += line + "\n"
        
        if is_need_wait:
            r.state = "waiting"
        else:
            r.state = "reponsed"

        return r

    async def role_post_msg(self,msg:AgentMsg,the_role:AIRole):
        msg.sender = the_role.get_role_id()
        
        target_role = self.role_group.get(msg.target)
        if target_role:
            msg.target = target_role.get_role_id()
            logger.info(f"{msg.sender} post message {msg.id} to inner role: {msg.target}")
            asyncio.create_task(self.role_process_msg(msg,target_role))
            return
        
        target_workflow = self.sub_workflows.get(msg.target)
        if target_workflow:
            msg.target = target_workflow.workflow_id
            logger.info(f"{msg.sender} post message {msg.id} to sub workflow: {msg.target}")
            asyncio.create_task(target_workflow._process_msg(msg))

        logger.info(f"{msg.sender} post message {msg.id} to AIBus: {msg.target}")
        await self.get_bus().post_message(msg.target,msg)
        return


    async def role_send_msg(self,msg:AgentMsg,the_role:AIRole):
        msg.sender = the_role.get_role_id()
        target_role = self.role_group.get(msg.target)
        if target_role:
            # msg.target = target_role.get_role_id()
            logger.info(f"{msg.sender} send message {msg.id} to inner role: {msg.target}")
            return await self.role_process_msg(msg,target_role)

        
        target_workflow = self.sub_workflows.get(msg.target)
        if target_workflow:
            # msg.target = target_workflow.workflow_id
            logger.info(f"{msg.sender} send message {msg.id} to sub workflow: {msg.target}")
            return await target_workflow._process_msg(msg)
        
        logger.info(f"{msg.sender} post message {msg.id} to AIBus: {msg.target}")
        return await self.get_bus().send_message(msg.target,msg)

    async def role_call(self,call:tuple,the_role:AIRole):
        logger.info(f"{the_role.role_id} call {call[0]} with args {call[1]}")
        return """{result:"timeout"}"""

    async def role_post_call(self,call:tuple,the_role:AIRole):
        logger.info(f"{the_role.role_id} post call {call[0]} with args {call[1]}")
        return


    async def role_process_msg(self,msg:AgentMsg,the_role:AIRole):
        session_topic = f"{msg.sender}#{msg.topic}"
        session_owner = the_role.get_role_id()
        chatsession : AIChatSession = AIChatSession.get_session(session_owner,session_topic,self.db_file)
        if chatsession is None:
            logger.error(f"get session {session_topic}@{session_owner} failed!")
            return None
   
        prompt = AgentPrompt()
        prompt.append(the_role.agent.prompt)
        prompt.append(self.get_workflow_rule_prompt())
        prompt.append(the_role.get_prompt())
        # prompt.append(self._get_function_prompt(the_role.get_name()))
        # prompt.append(self._get_knowlege_prompt(the_role.get_name()))
        prompt.append(await self._get_prompt_from_session(chatsession))

        msg_prompt = AgentPrompt()
        msg_prompt.messages = [{"role":"user","content":msg.body}]
        prompt.append(msg_prompt)
        
        
        async def _do_process_msg():
            #TODO: send msg to agent might be better?
            result_str = await ComputeKernel().do_llm_completion(prompt,the_role.agent.get_llm_model_name(),the_role.agent.get_max_token_size())
            result = Workflow.prase_llm_result(result_str)
            logger.info(f"{the_role.role_id} process {msg.sender}:{msg.body},llm str is :{result_str}")
            for postmsg in result.post_msgs:
                postmsg.topic = msg.topic
                await self.role_post_msg(postmsg,the_role)
                
            for post_call in result.post_calls:
                await self.role_post_call(post_call,the_role)
                
            result_prompt_str = ""
            match result.state:
                case "ignore":
                    return None
                case "reponsed":
                    resp_msg = AgentMsg()
                    resp_msg.topic = msg.topic
                    resp_msg.set(session_owner,msg.sender,result.resp)
            
                    chatsession.append_recv(msg)
                    chatsession.append_post(resp_msg)
                    return resp_msg
                case "waiting":
                    # TODO: Use role:"function" would be better
                    for sendmsg in result.send_msgs:
                        target = sendmsg.target
                        sendmsg.topic = msg.topic
                        send_resp = await self.role_send_msg(sendmsg,the_role)
                        if send_resp is not None:
                            result_prompt_str += f"\n{target} response is :{send_resp.body}"
                       
                    for call in result.calls:
                        call_result = await self.role_call(call,the_role)
                        if call_result is not None:
                            result_prompt_str += f"\ncall {call[0]} result is :{call_result}"

                    result_prompt = AgentPrompt()
                    result_prompt.messages = [{"role":"user","content":result_prompt_str}]
                    prompt.append(result_prompt)
                    r = await _do_process_msg()
                    return r
        
        return await _do_process_msg()

    async def _get_prompt_from_session(self,chatsession:AIChatSession) -> AgentPrompt:
        messages = chatsession.read_history() # read last 10 message
        result_prompt = AgentPrompt()
        for msg in reversed(messages):
            if msg.sender == chatsession.owner_id:
                result_prompt.messages.append({"role":"assistant","content":msg.body})
            else:
                result_prompt.messages.append({"role":"user","content":f"{msg.body}"})
        
        return result_prompt


    def _get_function_prompt(self,role_name:str) -> AgentPrompt:
        pass
    
    def _get_knowlege_prompt(self,role_name:str) -> AgentPrompt:
        pass


    def get_workflow_rule_prompt(self) -> AgentPrompt:
        return self.rule_prompt

    def _env_event_to_msg(self,env_event:EnvironmentEvent) -> AgentMsg:
        pass

    def get_inner_environment(self,env_id:str) -> Environment:
        pass

    def connect_to_environment(self,env:Environment) -> None:
        the_env = self.connected_environment.get(env.get_id())
        if the_env is None:
            self.connected_environment[env.get_id()] = env
            def _env_msg_handler(env_event:EnvironmentEvent) -> None:
                the_msg:AgentMsg= self._env_event_to_msg(env_event)
                self.post_msg(the_msg)
            
            # register all event handler
            the_env.attach_event_handler(None,_env_msg_handler)
        else:
            logger.warn(f"environment {env.get_id()} already connected!")

