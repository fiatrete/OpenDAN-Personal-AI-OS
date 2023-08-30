
import logging
import asyncio
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


class Workflow:
    def __init__(self) -> None:
        self.workflow_name : str = None
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

        #if config.get("rule_prompt") is None:
        #    logger.error("workflow config must have rule_prompt")
        #    return False
        #self.rule_prompt = AgentPrompt()
        #if self.rule_prompt.load_from_config(config.get("rule_prompt")) is False:
        #    logger.error("Workflow load rule_prompt failed")
        #    return False
        if config.get("roles") is None:
            logger.error("workflow config must have roles")
            return False
        self.role_group = AIRoleGroup()
        if self.role_group.load_from_config(config.get("roles")) is False:
            logger.error("Workflow load role_group failed")
            return False

        if config.get("input_filter") is not None:
            self.input_filter = MessageFilter()
            if self.input_filter.load_from_config(config.get("input_filter")) is False:
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

    async def _process_msg(self,msg:AgentMsg):
        final_result = None
        chatsession = None
        if self.input_filter is not None:
            select_role_id = self.input_filter.select(msg)
            if select_role_id is not None: 
                select_role = self.role_group.get(select_role_id)
                if select_role is None:
                    logger.error(f"input_filter return invalid role id:{select_role_id}, role not found in role_group")
                    return None

                result = await self._role_process_msg(msg,select_role)
                if result is None:
                    logger.error(f"_process_msg return None for :{msg}")
                    return
                if chatsession is not None:
                    chatsession.append_post(result)
                final_result = result
            else:
                logger.error(f"input_filter return None for :{msg}")
                return
                
        else:
            results = {}
            for this_role in self.role_group.roles.values():
                # TODO : we would do this in parallel
                a_result = await self._role_process_msg(msg,this_role)
                results[this_role.get_name()] = a_result

            # merge result from all roles 
            # TODO: one input msg can have multiple result msg, at this while ,we only support one result msg
            final_result:AgentMsg = self._merge_msg_result(results)
            if chatsession is not None:
                chatsession.append_post(final_result)
        
        return final_result




    async def _role_process_msg(self,msg:AgentMsg,the_role:AIRole) -> None:
        # TODO : we just record role's chatsession, but in future, we would record workflow's chatsession(like a groupo chat)
        session_topic = f"{the_role.get_name()}#{msg.sender}#{msg.topic}"
        chatsession = AIChatSession.get_session(self.workflow_name,session_topic,self.db_file)
        if chatsession is None:
            logger.error(f"get session {session_topic}@{self.workflow_name} failed!")
            return None
        
        # prompt generat progress is most important part of workflow(app) develope
        prompt = AgentPrompt()
        prompt.append(the_role.agent.prompt)
        prompt.append(the_role.get_prompt())

        # prompt.append(self.get_workflow_rule_prompt())
        # prompt.append(self._get_function_prompt(the_role.get_name()))
        # prompt.append(self._get_knowlege_prompt(the_role.get_name()))
        
        prompt.append(await self._get_prompt_from_session(chatsession))
        #prompt.append(await self._get_prompt_from_session(chatsession,the_role.get_name())) # chat context

        msg_prompt = AgentPrompt()
        msg_prompt.messages = [{"role":"user","content":msg.body}]
        prompt.append(msg_prompt)
        
        result = await ComputeKernel().do_llm_completion(prompt,the_role.agent.get_llm_model_name(),the_role.agent.get_max_token_size())
        chatsession.append_recv(msg)
        final_result = result        
      
        result_type : str = self._get_llm_result_type(result)
        is_ignore = False
        match result_type:
            case "function":
                callchain:CallChain = self._parse_function_call_chain(result)
                resp = await callchain.exec()
                if callchain.have_result():
                    # generator proc resp prompt with WAITING state
                    proc_resp_prompt:AgentPrompt = self._get_resp_prompt(resp,msg,the_role,prompt,chatsession)
                    final_result = await ComputeKernel().do_llm_completion(proc_resp_prompt,the_role.agent.get_llm_model_name(),the_role.agent.get_max_token_size())
                    return final_result

            
            case "send_message":
                # send message to other / sub workflow
                next_msg:AgentMsg = self._parse_to_msg(result)
                if next_msg is not None:
                    next_msg.sender = self.workflow_name
                    logger.info(f"W#{self.workflow_name} send message to {next_msg.get_target()}")
                    resp_msg = await self.get_bus().send_message(next_msg.get_target(),next_msg)
                    if resp_msg is not None:
                        msg_prompt = AgentPrompt()
                        msg_prompt.messages = [{"role":"assistant","content":result},{"role":"user","content":f"{next_msg.get_target()}:{resp_msg.body}"}]
                                               
                        final_result = await ComputeKernel().do_llm_completion(proc_resp_prompt,the_role.agent.get_llm_model_name(),the_role.agent.get_max_token_size())
                
                
            case "post_message":
                # post message to other / sub workflow
                next_msg:AgentMsg = self._parse_to_msg(result)
                if next_msg is not None:
                    next_msg.sender = self.workflow_name
                    logger.info(f"W#{self.workflow_name} post message to {next_msg.get_target()}")
                    self.get_bus().post_message(next_msg.get_target(),next_msg)

            case "ignore":
                is_ignore = True
                
        if is_ignore:
            return None
        
        resp_msg = AgentMsg()
        resp_msg.set(self.workflow_name,msg.sender,final_result)
        chatsession.append_post(resp_msg)
        return resp_msg

    async def _pop_msg(self) -> AgentMsg:
        pass

    def _get_chat_session_for_msg(self,msg:AgentMsg) -> AIChatSession:
        pass

    async def _get_prompt_from_session(self,chatsession:AIChatSession) -> AgentPrompt:
        messages = chatsession.read_history() # read last 10 message
        result_prompt = AgentPrompt()
        for msg in reversed(messages):
            if msg.target == chatsession.owner_id:
                result_prompt.messages.append({"role":"user","content":f"{msg.sender}:{msg.body}"})
            if msg.sender == chatsession.owner_id:
                result_prompt.messages.append({"role":"assistant","content":msg.body})
        
        return result_prompt
    
    def _get_msg_queue(self,session_id:str):
        pass

    def _merge_msg_result(self,results:dict) -> AgentMsg:
        # TODO: one input msg can have multiple result msg, at this while ,we only support one result msg
        for k,v in results.items():
            if v is not None:
                return v

    def _get_function_prompt(self,role_name:str) -> AgentPrompt:
        pass
    
    def _get_knowlege_prompt(self,role_name:str) -> AgentPrompt:
        pass

    def _get_resp_prompt(self,resp:str,msg:AgentMsg,role:AIRole,prompt:AgentPrompt) -> AgentPrompt:
        pass

    def get_workflow_rule_prompt(self) -> AgentPrompt:
        return self.rule_prompt
    
    def _get_llm_result_type(self,llm_resp_str:str) -> str:
        if llm_resp_str == "ignore":
            return "ignore"
        
        if llm_resp_str.find("sendmsg(") != -1:
            return "send_message"
        
        if llm_resp_str.find("postmsg(") != -1:
            return "post_message"
        
        if llm_resp_str.find("call(") != -1:
            return "function"
        
        return "text"

    def _parse_function_call_chain(self,llm_resp_str) -> CallChain:
        pass

    def _parse_to_msg(self,llm_resp_str) -> AgentMsg:
        lines = llm_resp_str.splitlines()
        for line in lines:
            if line.startswith("sendmsg("):
                line = line[8:]
                _index = line.find(",")
                msg = AgentMsg()
                msg.set("",line[:_index],line[_index+1:])
                return msg
            
            if line.startswith("postmsg("):
                line = line[8:]
                _index = line.find(",")
                msg = AgentMsg()
                msg.set("",line[:_index],line[_index+1:])
                return msg
        
        return None
    
    def get_workflow(self,workflow_name:str):
        """get workflow from known workflow list or sub workflow list"""
        pass


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

