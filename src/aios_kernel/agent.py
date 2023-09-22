from typing import Optional

from asyncio import Queue
import asyncio
import logging
import uuid
import time
import json
import shlex
import datetime

from .agent_message import AgentMsg, AgentMsgStatus, AgentMsgType,FunctionItem,LLMResult
from .chatsession import AIChatSession
from .compute_task import ComputeTaskResult
from .ai_function import AIFunction
from .environment import Environment
from .contact_manager import ContactManager,Contact,FamilyMember

logger = logging.getLogger(__name__)

class AgentPrompt:
    def __init__(self,prompt_str = None) -> None:
        self.messages = []
        if prompt_str:
            self.messages.append({"role":"user","content":prompt_str})
        self.system_message = None

    def as_str(self)->str:
        result_str = ""
        if self.system_message:
            result_str += self.system_message.get("role") + ":" + self.system_message.get("content") + "\n"
        if self.messages:
            for msg in self.messages:
                result_str += msg.get("role") + ":" + msg.get("content") + "\n"

        return result_str

    def to_message_list(self):
        result = []
        if self.system_message:
            result.append(self.system_message)
        result.extend(self.messages)
        return result

    def append(self,prompt):
        if prompt is None:
            return

        if prompt.system_message is not None:
            if self.system_message is None:
                self.system_message = prompt.system_message
            else:
                self.system_message["content"] += prompt.system_message.get("content")

        self.messages.extend(prompt.messages)

    def get_prompt_token_len(self):
        result = 0

        if self.system_message:
            result += len(self.system_message.get("content"))
        for msg in self.messages:
            result += len(msg.get("content"))

        return result

    def load_from_config(self,config:list) -> bool:
        if isinstance(config,list) is not True:
            logger.error("prompt is not list!")
            return False
        self.messages = []
        for msg in config:
            if msg.get("role") == "system":
                self.system_message = msg
            else:
                self.messages.append(msg)
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
        self.enable_kb = False
        self.enable_timestamp = False
        self.guest_prompt_str = None 
        self.owner_promp_str = None
        self.contact_prompt_str = None

        self.chat_db = None
        self.unread_msg = Queue() # msg from other agent
        self.owner_env : Environment = None
        self.owenr_bus = None
        self.enable_function_list = []

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

        if config.get("guest_prompt") is not None:
            self.guest_prompt_str = config["guest_prompt"]

        if config.get("owner_prompt") is not None:
            self.owner_promp_str = config["owner_prompt"]
        
        if config.get("contact_prompt") is not None:
            self.contact_prompt_str = config["contact_prompt"]

        if config.get("owner_env") is not None:
            self.owner_env = Environment.get_env_by_id(config["owner_env"])

        if config.get("powerby") is not None:
            self.powerby = config["powerby"]
        if config.get("template_id") is not None:
            self.template_id = config["template_id"]
        if config.get("llm_model_name") is not None:
            self.llm_model_name = config["llm_model_name"]
        if config.get("max_token_size") is not None:
            self.max_token_size = config["max_token_size"]
        if config.get("enable_function") is not None:
            self.enable_function_list = config["enable_function"]
        if config.get("enable_kb") is not None:
            self.enable_kb = bool(config["enable_kb"])
        if config.get("enable_timestamp") is not None:
            self.enable_timestamp = bool(config["enable_timestamp"])
        return True


    def _get_llm_result_type(self,llm_result_str:str) -> LLMResult:
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
                    new_msg.set(self.agent_id,target_id,msg_content)

                    r.send_msgs.append(new_msg)
                    is_need_wait = True

                case "post_msg":# postmsg($target_id,$msg_content)
                    if len(func_args) != 1:
                        logger.error(f"parse postmsg failed! {func_call}")
                        return False
                    new_msg = AgentMsg()
                    target_id = func_item.args[0]
                    msg_content = func_item.body
                    new_msg.set(self.agent_id,target_id,msg_content)
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
    
    def _get_remote_user_prompt(self,remote_user:str) -> AgentPrompt:
        cm = ContactManager.get_instance()
        contact = cm.find_contact_by_name(remote_user)
        if contact is None:
            #create guest prompt
            if self.guest_prompt_str is not None:
                prompt = AgentPrompt()
                prompt.system_message = {"role":"system","content":self.guest_prompt_str}
                return prompt
            return None
        else:
            if contact.is_family_member:
                if self.owner_promp_str is not None:
                    real_str = self.owner_promp_str.format_map(contact.to_dict())
                    prompt = AgentPrompt()
                    prompt.system_message = {"role":"system","content":real_str}
                    return prompt
            else:
                if self.contact_prompt_str is not None:
                    real_str = self.contact_prompt_str.format_map(contact.to_dict())
                    prompt = AgentPrompt()
                    prompt.system_message = {"role":"system","content":real_str}
                    return prompt
                
        return None

    def _get_inner_functions(self) -> dict:
        if self.owner_env is None:
            return None

        all_inner_function = self.owner_env.get_all_ai_functions()
        if all_inner_function is None:
            return None

        result_func = []
        result_len = 0
        for inner_func in all_inner_function:
            func_name = inner_func.get_name()
            if self.enable_function_list is not None:
                if len(self.enable_function_list) > 0:
                    if func_name not in self.enable_function_list:
                        logger.debug(f"ageint {self.agent_id} ignore inner func:{func_name}")
                        continue
                else:
                    continue
            this_func = {}
            this_func["name"] = func_name
            this_func["description"] = inner_func.get_description()
            this_func["parameters"] = inner_func.get_parameters()
            result_len += len(json.dumps(this_func)) / 4
            result_func.append(this_func)

        return result_func,result_len

    async def _execute_func(self,inenr_func_call_node:dict,prompt:AgentPrompt,org_msg:AgentMsg,stack_limit = 5) -> str:
        from .compute_kernel import ComputeKernel
 
        func_name = inenr_func_call_node.get("name")
        arguments = json.loads(inenr_func_call_node.get("arguments"))
        logger.info(f"llm execute inner func:{func_name} ({json.dumps(arguments)})")

        func_node : AIFunction = self.owner_env.get_ai_function(func_name)
        if func_node is None:
            return "execute failed,function not found"

        ineternal_call_record = AgentMsg.create_internal_call_msg(func_name,arguments,org_msg.get_msg_id(),org_msg.target)
        try:
            result_str:str = await func_node.execute(**arguments)
        except Exception as e:
            result_str = "call error:" + str(e)
            logger.error(f"llm execute inner func:{func_name} error:{e}")


        logger.info("llm execute inner func result:" + result_str)
        inner_functions,inner_function_len = self._get_inner_functions()
        prompt.messages.append({"role":"function","content":result_str,"name":func_name})
        task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,self.llm_model_name,self.max_token_size,inner_functions)

        ineternal_call_record.result_str = task_result.result_str
        ineternal_call_record.done_time = time.time()
        org_msg.inner_call_chain.append(ineternal_call_record)

        if stack_limit > 0:
            inner_func_call_node = task_result.result_message.get("function_call")

        if inner_func_call_node:
            return await self._execute_func(inner_func_call_node,prompt,org_msg,stack_limit-1)
        else:
            return task_result.result_str

    async def _get_agent_prompt(self) -> AgentPrompt:
        return self.prompt

    def _format_msg_by_env_value(self,prompt:AgentPrompt):
        if self.owner_env is None:
            return

        for msg in prompt.messages:
            old_content = msg.get("content")
            msg["content"] = old_content.format_map(self.owner_env)

    async def _get_knowlege_prompt(self,input_msg:AgentPrompt) -> AgentPrompt:
        if self.enable_kb is False:
            return None
        
        from .knowledge_base import KnowledgeBase
        return await KnowledgeBase().query_prompt(input_msg)

    async def _process_msg(self,msg:AgentMsg) -> AgentMsg:
            from .compute_kernel import ComputeKernel
            from .bus import AIBus
            
            session_topic = msg.get_sender() + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.chat_db)
            if msg.mentions is not None:
                if not self.agent_id in msg.mentions:
                    chatsession.append(msg)
                    logger.info(f"agent {self.agent_id} recv a group chat message from {msg.sender},but is not mentioned,ignore!")
                    return None
                
            msg_prompt = AgentPrompt()
            msg_prompt.messages = [{"role":"user","content":msg.body}]

            prompt = AgentPrompt()
            prompt.append(await self._get_agent_prompt())
            self._format_msg_by_env_value(prompt)
            prompt.append(self._get_remote_user_prompt(msg.sender))

            inner_functions,function_token_len = self._get_inner_functions()
       
            system_prompt_len = prompt.get_prompt_token_len()
            input_len = len(msg.body)

            history_prmpt,history_token_len = await self._get_prompt_from_session(chatsession,system_prompt_len + function_token_len,input_len)
            prompt.append(history_prmpt) # chat context
            
            kb_prompt = await self._get_knowlege_prompt(msg_prompt)
            prompt.append(kb_prompt)
            prompt.append(msg_prompt)


            logger.debug(f"Agent {self.agent_id} do llm token static system:{system_prompt_len},function:{function_token_len},history:{history_token_len},input:{input_len}，totoal prompt:{system_prompt_len + function_token_len + history_token_len} ")
            task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,self.llm_model_name,self.max_token_size,inner_functions)
            final_result = task_result.result_str

            inner_func_call_node = task_result.result_message.get("function_call")
            if inner_func_call_node:
                #TODO to save more token ,can i use msg_prompt?
                final_result = await self._execute_func(inner_func_call_node,prompt,msg)

            llm_result : LLMResult = self._get_llm_result_type(final_result)
            is_ignore = False
            result_prompt_str = ""
            match llm_result.state:
                case "ignore":
                    is_ignore = True
                case "waiting":
                    for sendmsg in llm_result.send_msgs:
                        target = sendmsg.target
                        sendmsg.topic = msg.topic
                        sendmsg.prev_msg_id = msg.get_msg_id()
                        send_resp = await AIBus.get_default_bus().send_message(sendmsg)
                        if send_resp is not None:
                            result_prompt_str += f"\n{target} response is :{send_resp.body}"
                            agent_sesion = AIChatSession.get_session(self.agent_id,f"{sendmsg.target}#{sendmsg.topic}",self.chat_db)
                            agent_sesion.append(sendmsg)
                            agent_sesion.append(send_resp)

                    final_result = llm_result.resp + result_prompt_str

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

    async def _get_prompt_from_session(self,chatsession:AIChatSession,system_token_len,input_token_len,is_groupchat=False) -> AgentPrompt:
        # TODO: get prompt from group chat is different from single chat
        history_len = (self.max_token_size * 0.7) - system_token_len - input_token_len
        messages = chatsession.read_history() # read
        result_token_len = 0
        result_prompt = AgentPrompt()
        read_history_msg = 0
        for msg in reversed(messages):
            read_history_msg += 1
            dt = datetime.datetime.fromtimestamp(float(msg.create_time))
            formatted_time = dt.strftime('%m-%d %H:%M:%S')

            if msg.sender == self.agent_id:

                if self.enable_timestamp:
                    result_prompt.messages.append({"role":"assistant","content":f"(create on {formatted_time}) {msg.body} "})
                else:
                    result_prompt.messages.append({"role":"assistant","content":msg.body})
                
            else:
                if self.enable_timestamp:
                    result_prompt.messages.append({"role":"user","content":f"(create on {formatted_time}) {msg.body} "})
                else:
                    result_prompt.messages.append({"role":"user","content":msg.body})

            history_len -= len(msg.body)
            result_token_len += len(msg.body)
            if history_len < 0:
                logger.warning(f"_get_prompt_from_session reach limit of token,just read {read_history_msg} history message.")
                break

        return result_prompt,result_token_len

