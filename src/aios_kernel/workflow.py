
import logging
import asyncio
from typing import Optional,Tuple

from .environment import Environment,EnvironmentEvent
from .agent import AgentPrompt,AgentMsg,AIChatSession
from .role import AIRole
from .ai_function import CallChain
from .compute_kernel import ComputeKernel

logger = logging.getLogger(__name__)

class MessageFilter:
    def __init__(self) -> None:
        pass
    def select(self,msg:AgentMsg) -> AIRole:
        pass

class Workflow:
    def __init__(self) -> None:
        self.rule_prompt : AgentPrompt = None
        self.workflow_config = None
        self.role_group = None
        self.input_filter : MessageFilter= None
        self.msg_queue = []
        self.connected_environment = {}
        
    def load_from_disk(self,config_path:str,context_dir_path) -> int:
        pass

    #workflow is asynchronous. 
    # When processing one message, it can process another message at the same time. 
    # chatsession is synchronous, it has to wait for the previous message to finish processing before it can process the next message. 
    # Therefore, post a message needs to specify the session_id explicitly, if not specified it will be automatically created by workflow.
    def post_msg(self,msg:AgentMsg) -> None:
        self.msg_queue.append(msg)
        return
    
    async def send_msg(self,msg:AgentMsg) -> str:
        pass
    
    async def run(self):
        # TODO add tracking design of msg processing
        while True:
            the_msg = await self._pop_msg()
            chatsession:AIChatSession = self._get_chat_session_for_msg(the_msg)
            if chatsession is None:
                logger.error(f"get_chat_session_for_msg return None for :{the_msg}")
                continue

            chatsession.append_recv(the_msg)
        
            async def _process_msg(msg:AgentMsg,the_role) -> None:
                # prompt generat progress is most important part of workflow(app) develope
                prompt = AgentPrompt()
                prompt.append(the_role.get_prompt())
                prompt.append(self.get_workflow_rule_prompt())
                prompt.append(self._get_function_prompt(the_role.get_name()))
                prompt.append(self._get_knowlege_prompt(the_role.get_name()))
                prompt.append(await self._get_prompt_from_session(chatsession,the_role.get_name())) # chat context

                result = await ComputeKernel().do_llm_completion(prompt,the_role.agent.get_llm_model_name(),the_role.agent.get_max_token_size())
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
                            # TODO: Next Target can be another role in workflow
                            next_workflow:Workflow = self.get_workflow(next_msg.get_target())
                            inner_chat_session = the_role.agent.get_chat_session(next_msg.get_target(),next_msg.get_session_id())

                            inner_chat_session.append_post(next_msg)
                            resp = await next_workflow.send_msg(next_msg)
                            inner_chat_session.append_recv(resp)
                            # generator proc resp prompt with WAITING state
                            proc_resp_prompt:AgentPrompt = self._get_resp_prompt(resp,msg,the_role,prompt,chatsession)
                            final_result = await ComputeKernel().do_llm_completion(proc_resp_prompt,the_role.agent.get_llm_model_name(),the_role.agent.get_max_token_size())
                           
                            return final_result
                        
                    case "post_message":
                        # post message to other / sub workflow
                        next_msg:AgentMsg = self._parse_to_msg(result)
                        if next_msg is not None:
                            next_workflow:Workflow = self.get_workflow(next_msg.get_target())
                            inner_chat_session = the_role.agent.get_chat_session(next_msg.get_target(),next_msg.get_session_id())
                            inner_chat_session.append_post(next_msg)
                            next_workflow.post_msg(next_msg)

                    case "ignore":
                        is_ignore = True
                        
                if is_ignore is not True:
                    # TODO : how to get inner chat session?
                    inner_chat_session = the_role.agent.get_chat_session_for_msg(msg)
                    if inner_chat_session is not None:
                        inner_chat_session.append_input(msg)
                        inner_chat_session.append_result(final_result)

                return result
    
            async def _workflow_process_msg(msg:AgentMsg) -> None:
                final_result = None
                if self.input_filter is not None:
                    select_role = self.input_filter.select(msg)
                    if select_role is not None: 
                        result = await _process_msg(msg,select_role)
                        if result is None:
                            logger.error(f"_process_msg return None for :{msg}")
                            return
                        if chatsession is not None:
                            chatsession.append_post(result)
                        final_result = result
                        
                else:
                    results = {}
                    for this_role in self.role_group.roles:
                        a_result = asyncio.create_task(_process_msg(msg,this_role))
                        results[this_role.get_name()] = a_result

                    # merge result from all roles 
                    # TODO: one input msg can have multiple result msg, at this while ,we only support one result msg
                    final_result:AgentMsg = self._merge_msg_result(results)
                    if chatsession is not None:
                        chatsession.append_post(final_result)

                if final_result is not None:
                    # TODO post message to source
                    pass 
              
            asyncio.create_task(_workflow_process_msg(the_msg))

    async def _pop_msg(self) -> AgentMsg:
        pass

    def _get_chat_session_for_msg(self,msg:AgentMsg) -> AIChatSession:
        pass

    async def _get_prompt_from_session(self,chatsession:AIChatSession,role_name:str) -> AgentPrompt:
        pass
    
    def _get_msg_queue(self,session_id:str):
        pass

    def _merge_msg_result(self,results:dict) -> AgentMsg:
        pass

    def _get_function_prompt(self,role_name:str) -> AgentPrompt:
        pass
    
    def _get_knowlege_prompt(self,role_name:str) -> AgentPrompt:
        pass

    def _get_resp_prompt(self,resp:str,msg:AgentMsg,role:AIRole,prompt:AgentPrompt,chatsession:AIChatSession) -> AgentPrompt:
        pass

    def get_workflow_rule_prompt(self) -> AgentPrompt:
        return self.rule_prompt
    
    def _get_llm_result_type(self,llm_resp_str:str) -> str:
        pass

    def _parse_function_call_chain(self,llm_resp_str) -> CallChain:
        pass

    def _parse_to_msg(self,llm_resp_str) -> AgentMsg:
        pass
    
    def get_workflow(self,workflow_name:str) -> Workflow:
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

