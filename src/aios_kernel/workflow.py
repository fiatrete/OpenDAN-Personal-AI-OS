import logging
import asyncio
import json
import os
import time
from asyncio import Queue
from typing import Optional,Tuple,List
from abc import ABC, abstractmethod

from .environment import Environment,EnvironmentEvent
from .agent_message import AgentMsg,AgentMsgStatus,FunctionItem,LLMResult
from .agent import AgentPrompt,AgentMsg
from .chatsession import AIChatSession
from .role import AIRole,AIRoleGroup
from .ai_function import AIFunction,FunctionItem
from .compute_kernel import ComputeKernel
from .compute_task import ComputeTask,ComputeTaskResult,ComputeTaskState,ComputeTaskResultCode
from .bus import AIBus
from .workflow_env import WorkflowEnvironment


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
        self.workflow_id : str = None
        self.rule_prompt : AgentPrompt = None
        self.workflow_config = None
        self.role_group : dict = None
        self.input_filter : MessageFilter= None
        self.connected_environment = {}
        self.sub_workflows = {}
        self.owner_workflow = None
        self.db_file = None
        self.env_db_file = None
        self.workflow_env:WorkflowEnvironment = None

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

        if self.owner_workflow is None:
            self.env_db_file = os.path.dirname(self.db_file) + "/" + self.workflow_id + "_env.db"
        else:
            self.env_db_file = self.owner_workflow.env_db_file
        self.workflow_env = WorkflowEnvironment(self.workflow_id,self.env_db_file)

        env_ndoe = config.get("enviroment")
        if  env_ndoe is not None:
            if self._load_env_from_config(env_ndoe) is False:
                logger.error("Workflow load env failed")
                return False

        connected_env_ndoe = config.get("connected_env")
        if  connected_env_ndoe is not None:
           for _node in connected_env_ndoe:
                env_id = _node.get("env_id")
                if env_id is None:
                    continue

                remote_env = Environment.get_env_by_id(env_id)
                if remote_env is None:
                     logger.error(f"Workflow load connected_env failed, env {env_id} not found!")
                     return False
                self.connect_to_environment(remote_env,_node.get("event2msg"))

        sub_workflows = config.get("sub_workflows")
        if sub_workflows is not None:
            if self._load_sub_workflows(sub_workflows) is False:
                logger.error("Workflow load sub workflows failed")
                return False

        return True

    def _load_env_from_config(self,config:dict) -> bool:
        for k,v in config.items():
            self.workflow_env.set_value(k,v,False)

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
                current_workflow_chatsession = AIChatSession.get_session(current_workflow.workflow_id,msg.sender + "#" + msg.topic,current_workflow.db_file)
                if the_role is not None:
                    return await current_workflow.role_process_msg(msg,the_role,current_workflow_chatsession)
                sub_workflow = current_workflow.sub_workflows.get(inner_obj_id[i])
                if sub_workflow is not None:
                    return await sub_workflow._process_msg(msg)
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

    def get_workflow_id_from_target(self,target:str) -> str:
        target_list = target.split(".")
        if len(target_list) == 0:
            return target
        else:
            result_str = ""
            p = 0
            for s in target_list:
                p = p + 1
                result_str += s
                if p < len(target_list)-1:
                    result_str += "."
                else:
                    return result_str

    async def _process_msg(self,msg:AgentMsg) -> AgentMsg:
        real_target = msg.target.split(".")[0]
        targets = self._parse_msg_target(msg.target)
        if len(targets) > 1:
            return await self._forword_msg(targets,msg)
        
        #0 we don't support workflow join a group right now, this cloud be a feture in future
        if msg.mentions is not None:
            logger.warn(f"workflow {self.workflow_id} recv a group chat message,not support ignore!")
            error_resp = msg.create_error_resp(f"workflow {self.workflow_id} recv a group chat message,not support ignore!")
            return error_resp

        #1. workflow start process message
        # this is workflow's group_chat session
        session_topic = msg.sender + "#" + msg.topic
        chatsesssion = AIChatSession.get_session(self.workflow_id,session_topic,self.db_file)

        #2. find role by msg.mentions or workflow's selector logic
        if msg.mentions is not None:
            if not self.workflow_id in msg.mentions:
                chatsesssion.append(msg)
                logger.info(f"workflow {self.workflow_id} recv a group chat message from {msg.sender},but is not mentioned,ignore!")
                return None

            for mention in msg.mentions:
                this_role = self.role_group.get(mention)
                if this_role is not None:
                    return await self.role_process_msg(msg,this_role,chatsesssion)

        if self.input_filter is not None:
            select_role_id = self.input_filter.select(msg)
            if select_role_id is not None:
                select_role = self.role_group.get(select_role_id)
                if select_role is None:
                    logger.error(f"input_filter return invalid role id:{select_role_id}, role not found in role_group")
                    return None

                return await self.role_process_msg(msg,select_role,chatsesssion)
            else:
                logger.error(f"input_filter return None for :{msg.body}")
                return None

        err_str = f"{self.workflow_id}:no role can process this msg:{msg.body}"
        logger.error(err_str)
        error_resp = msg.create_error_resp(err_str)
        return error_resp

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

        def check_args(func_item:FunctionItem):
            match func_name:
                case "send_msg":# sendmsg($target_id,$msg_content)
                    if len(func_args) != 1:
                        logger.error(f"parse sendmsg failed! {func_call}")
                        return False
                    new_msg = AgentMsg()
                    target_id = func_item.args[0]
                    msg_content = func_item.body
                    new_msg.set("_",target_id,msg_content)

                    r.send_msgs.append(new_msg)
                    is_need_wait = True

                case "post_msg":# postmsg($target_id,$msg_content)
                    if len(func_args) != 1:
                        logger.error(f"parse postmsg failed! {func_call}")
                        return False
                    new_msg = AgentMsg()
                    target_id = func_item.args[0]
                    msg_content = func_item.body
                    new_msg.set("_",target_id,msg_content)
                    r.post_msgs.append(new_msg)

                case "call":# call($func_name,$args_str)
                    r.calls.append(func_item)
                    is_need_wait = True
                    return True
                case "post_call": # post_call($func_name,$args_str)
                    r.post_calls.append(func_item)
                    return True

        current_func : FunctionItem = None
        for line in lines:
            if line.startswith("##/"):
                if current_func:
                    if check_args(current_func) is False:
                        r.resp += current_func.dumps()

                func_name,func_args = AgentMsg.parse_function_call(line[3:])
                current_func = FunctionItem(func_name,func_args)
            else:
                if current_func:
                    current_func.append_body(line + "\n")
                else:
                    r.resp += line + "\n"

        if current_func:
            if check_args(current_func) is False:
                r.resp += current_func.dumps()

        if len(r.send_msgs) > 0 or len(r.calls) > 0:
            r.state = "waiting"
        else:
            r.state = "reponsed"

        return r

    async def role_post_msg(self,msg:AgentMsg,the_role:AIRole,workflow_chat_session:AIChatSession):
        msg.sender = the_role.get_role_id()

        target_role = self.role_group.get(msg.target)
        if target_role:
            msg.target = target_role.get_role_id()
            logger.info(f"{msg.sender} post message {msg.msg_id} to inner role: {msg.target}")
            asyncio.create_task(self.role_process_msg(msg,target_role,workflow_chat_session))
            return

        target_workflow = self.sub_workflows.get(msg.target)
        if target_workflow:
            msg.target = target_workflow.workflow_id
            logger.info(f"{msg.sender} post message {msg.msg_id} to sub workflow: {msg.target}")
            asyncio.create_task(target_workflow._process_msg(msg))

        logger.info(f"{msg.sender} post message {msg.msg_id} to AIBus: {msg.target}")
        await self.get_bus().post_message(msg,msg.target)
        return


    async def role_send_msg(self,msg:AgentMsg,the_role:AIRole,workflow_chat_session:AIChatSession):
        msg.sender = the_role.get_role_id()
        target_role = self.role_group.get(msg.target)
        if target_role:
            # msg.target = target_role.get_role_id()
            logger.info(f"{msg.sender} send message {msg.msg_id} to inner role: {msg.target}")
            return await self.role_process_msg(msg,target_role,workflow_chat_session)

        target_workflow = self.sub_workflows.get(msg.target)
        if target_workflow:
            # msg.target = target_workflow.workflow_id
            logger.info(f"{msg.sender} send message {msg.msg_id} to sub workflow: {msg.target}")
            return await target_workflow._process_msg(msg)

        logger.info(f"{msg.sender} post message {msg.msg_id} to AIBus: {msg.target}")
        return await self.get_bus().send_message(msg)

    async def role_call(self,func_item:FunctionItem,the_role:AIRole):
        logger.info(f"{the_role.role_id} call {func_item.name} ")
        arguments = func_item.args

        func_node : AIFunction = self.workflow_env.get_ai_function(func_item.name)
        if func_node is None:
            return "execute failed,function not found"

        result_str:str = await func_node.execute(**arguments)
        return result_str

    async def role_post_call(self,func_item:FunctionItem,the_role:AIRole):
        logger.info(f"{the_role.role_id} post call {func_item.name} ")
        return await self.role_call(func_item,the_role)

    def _format_msg_by_env_value(self,prompt:AgentPrompt):
        if self.workflow_env is None:
            return

        for msg in prompt.messages:
            old_content = msg.get("content")
            msg["content"] = old_content.format_map(self.workflow_env)

    def _get_inner_functions(self,the_role:AIRole) -> dict:
        all_inner_function = self.workflow_env.get_all_ai_functions()
        if all_inner_function is None:
            return None

        result_func = []
        for inner_func in all_inner_function:
            func_name = inner_func.get_name()
            if the_role.enable_function_list is not None:
                if len(the_role.enable_function_list) > 0:
                    if func_name not in the_role.enable_function_list:
                        logger.debug(f"agent {self.agent_id} ignore inner func:{func_name}")
                        continue
                else:
                    continue
            this_func = {}
            this_func["name"] = func_name
            this_func["description"] = inner_func.get_description()
            this_func["parameters"] = inner_func.get_parameters()
            result_func.append(this_func)
        if len(result_func) > 0:
            return result_func
        return None

    async def _role_execute_func(self,the_role:AIRole,inenr_func_call_node:dict,prompt:AgentPrompt,org_msg:AgentMsg,stack_limit = 5) -> [str,int]:
        from .compute_kernel import ComputeKernel

        func_name = inenr_func_call_node.get("name")
        arguments = json.loads(inenr_func_call_node.get("arguments"))
        ineternal_call_record = AgentMsg.create_internal_call_msg(func_name,arguments,org_msg.get_msg_id(),org_msg.target)
        func_node : AIFunction = self.workflow_env.get_ai_function(func_name)
        result_str : str = ""
        if func_node is None:
            result_str = f"execute {func_name} failed,function not found"
        else:
            try:
                result_str = await func_node.execute(**arguments)
            except Exception as e:
                result_str = f"execute {func_name} error:{str(e)}"
                logger.error(f"llm execute inner func:{func_name} error:{e}")


        inner_functions = self._get_inner_functions(the_role)
        prompt.messages.append({"role":"function","content":result_str,"name":func_name})
        task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,
                                                                                the_role.agent.llm_model_name,the_role.agent.max_token_size,
                                                                                inner_functions)
        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"llm compute error:{task_result.error_str}")
            return task_result.error_str,1

        ineternal_call_record.result_str = task_result.result_str
        ineternal_call_record.done_time = time.time()
        org_msg.inner_call_chain.append(ineternal_call_record)
        if stack_limit > 0:
            result_message = task_result.result.get("message")
            if result_message:
                inner_func_call_node = result_message.get("function_call")

        if inner_func_call_node:
            return await self._role_execute_func(the_role,inner_func_call_node,prompt,org_msg,stack_limit-1)
        else:
            return task_result.result_str,0

    def _is_in_same_workflow(self,msg) -> bool:
        pass

    async def role_process_msg(self,msg:AgentMsg,the_role:AIRole,workflow_chat_session:AIChatSession) -> AgentMsg:
        msg.target = the_role.get_role_id()


        prompt = AgentPrompt()
        prompt.append(the_role.agent.prompt)
        prompt.append(self.get_workflow_rule_prompt())
        prompt.append(the_role.get_prompt())
        # prompt.append(self._get_function_prompt(the_role.get_name()))
        # prompt.append(self._get_knowlege_prompt(the_role.get_name()))

        #support group chat, user content include sender name!
        prompt.append(await self._get_prompt_from_session(the_role,workflow_chat_session))

        msg_prompt = AgentPrompt()
        msg_prompt.messages = [{"role":"user","content":f"user name is {msg.sender}, his question is :{msg.body}"}]
        prompt.append(msg_prompt)

        self._format_msg_by_env_value(prompt)
        inner_functions = self._get_inner_functions(the_role)

        async def _do_process_msg():
            #TODO: send msg to agent might be better?
            task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,the_role.agent.get_llm_model_name(),the_role.agent.get_max_token_size(),inner_functions)
            if task_result.result_code != ComputeTaskResultCode.OK:
                logger.error(f"llm compute error:{task_result.error_str}")
                error_resp = msg.create_error_resp(task_result.error_str)
                return error_resp
            
            result_str = task_result.result_str
            logger.info(f"{the_role.role_id} process {msg.sender}:{msg.body},llm str is :{result_str}")

            result_message = task_result.result.get("message")
            if result_message:
                inner_func_call_node = result_message.get("function_call")

            if inner_func_call_node:
                #TODO to save more token ,can i use msg_prompt?
                result_str,r_code = await self._role_execute_func(the_role,inner_func_call_node,prompt,msg)
                if r_code != 0:
                    error_resp = msg.create_error_resp(result_str)
                    return error_resp

            result : LLMResult = Workflow.prase_llm_result(result_str)
            for postmsg in result.post_msgs:
                postmsg.prev_msg_id = msg.get_msg_id()
                # might be craete a new msg.topic for this postmsg
                postmsg.topic = msg.topic

                await self.role_post_msg(postmsg,the_role,workflow_chat_session)
                if not self._is_in_same_workflow(postmsg):
                    role_sesion = AIChatSession.get_session(the_role.get_role_id(),f"{postmsg.target}#{msg.topic}",self.db_file)
                    role_sesion.append(postmsg)
                else:
                    # message will be saved in role.process_message
                    pass


            for post_call in result.post_calls:
                action_msg = msg.create_action_msg(post_call[0],post_call[1],the_role.get_role_id())
                workflow_chat_session.append(action_msg)
                await self.role_post_call(post_call,the_role)
                #save post_call

            result_prompt_str = ""
            match result.state:
                case "ignore":
                    return None
                case "reponsed":
                    resp_msg = msg.create_resp_msg(result.resp)
                    resp_msg.sender = the_role.get_role_id()
                    # It is always the person handling the messages who puts them into the session.
                    workflow_chat_session.append(msg)
                    workflow_chat_session.append(resp_msg)
                    #await self.get_bus().resp_message(resp_msg)
                    return resp_msg
                case "waiting":        
                    for sendmsg in result.send_msgs:
                        target = sendmsg.target
                        sendmsg.topic = msg.topic
                        sendmsg.prev_msg_id = msg.get_msg_id()
                        send_resp = await self.role_send_msg(sendmsg,the_role,workflow_chat_session)
                        if send_resp is not None:
                            result_prompt_str += f"\n# {target} response is : \n{send_resp.body}"

                        if not self._is_in_same_workflow(sendmsg):
                            role_sesion = AIChatSession.get_session(the_role.get_role_id(),f"{sendmsg.target}#{sendmsg.topic}",self.db_file)
                            role_sesion.append(sendmsg)
                            role_sesion.append(send_resp)
                        else:
                             # message will be saved in role.process_message
                            pass
                    
                    this_llm_resp_prompt = AgentPrompt()
                    this_llm_resp_prompt.messages = [{"role":"assistant","content":result_str}]
                    prompt.append(this_llm_resp_prompt)

                    result_prompt = AgentPrompt()
                    result_prompt.messages = [{"role":"user","content":result_prompt_str}]
                    prompt.append(result_prompt)
                    return await _do_process_msg()

        return await _do_process_msg()

    async def _get_prompt_from_session(self,the_role:AIRole,chatsession:AIChatSession) -> AgentPrompt:
        messages = chatsession.read_history(the_role.history_len) # read last 10 message
        result_prompt = AgentPrompt()
        for msg in reversed(messages):
            if msg.sender == chatsession.owner_id:
                result_prompt.messages.append({"role":"assistant","content":msg.body})
            else:
                result_prompt.messages.append({"role":"user","content":f"{msg.body}"})

        return result_prompt

    def _get_knowlege_prompt(self,role_name:str) -> AgentPrompt:
        pass

    def get_workflow_rule_prompt(self) -> AgentPrompt:
        return self.rule_prompt

    def _env_event_to_msg(self,env_event:EnvironmentEvent) -> AgentMsg:
        pass

    def get_inner_environment(self,env_id:str) -> Environment:
        pass

    def connect_to_environment(self,the_env:Environment,conn_info:dict) -> None:
        if the_env is not None:
            self.workflow_env.add_owner_env(the_env)

            #for event2msg in conn_info:
            #    for k,v in event2msg:
            #        if k == "role":
            #            continue
            #        else:
            #
            #            def _env_msg_handler(env_event:EnvironmentEvent) -> None:
            #                the_msg:AgentMsg= self._env_event_to_msg(env_event)
            #                self.role_post_msg

            #            the_env.attach_event_handler(k,_env_msg_handler)
            #            break





