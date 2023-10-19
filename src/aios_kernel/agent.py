from typing import Optional

from asyncio import Queue
import asyncio
import logging
import uuid
import time
import json
import shlex
import datetime
import copy

from .agent_base import AgentMsg, AgentMsgStatus, AgentMsgType,FunctionItem,LLMResult,AgentPrompt
from .chatsession import AIChatSession
from .compute_task import ComputeTaskResult,ComputeTaskResultCode
from .ai_function import AIFunction
from .environment import Environment
from .contact_manager import ContactManager,Contact,FamilyMember
from .compute_kernel import ComputeKernel
from .bus import AIBus

from knowledge import *

logger = logging.getLogger(__name__)


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
        self.role_prompt:AgentPrompt = None
        self.agent_prompt:AgentPrompt = None
        self.agent_think_prompt:AgentPrompt = None
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
        self.history_len = 10

        self.learn_token_limit = 500
        self.learn_prompt = None

        self.chat_db = None
        self.unread_msg = Queue() # msg from other agent
        self.owner_env : Environment = None
        self.owenr_bus = None
        self.enable_function_list = None

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
        result_agent.agent_prompt = templete.prompt
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
            self.agent_prompt = AgentPrompt()
            self.agent_prompt.load_from_config(config["prompt"])
        
        if config.get("think_prompt") is not None:
            self.agent_think_prompt = AgentPrompt()
            self.agent_think_prompt.load_from_config(config["think_prompt"])

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
        if config.get("history_len"):
            self.history_len = int(config.get("history_len"))
        return True
    
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
    
    def get_llm_learn_token_limit(self) -> int:
        return self.learn_token_limit
    
    def get_learn_prompt(self) -> AgentPrompt:
        return self.learn_prompt
    
    def get_agent_role_prompt(self) -> AgentPrompt:
        return self.role_prompt

    
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
            return None,0

        all_inner_function = self.owner_env.get_all_ai_functions()
        if all_inner_function is None:
            return None,0

        result_func = []
        result_len = 0
        for inner_func in all_inner_function:
            func_name = inner_func.get_name()
            if self.enable_function_list is not None:
                if len(self.enable_function_list) > 0:
                    if func_name not in self.enable_function_list:
                        logger.debug(f"ageint {self.agent_id} ignore inner func:{func_name}")
                        continue

            this_func = {}
            this_func["name"] = func_name
            this_func["description"] = inner_func.get_description()
            this_func["parameters"] = inner_func.get_parameters()
            result_len += len(json.dumps(this_func)) / 4
            result_func.append(this_func)

        return result_func,result_len

    async def _execute_func(self,inner_func_call_node:dict,prompt:AgentPrompt,inner_functions,org_msg:AgentMsg=None,stack_limit = 5) -> ComputeTaskResult:
        func_name = inner_func_call_node.get("name")
        arguments = json.loads(inner_func_call_node.get("arguments"))
        logger.info(f"llm execute inner func:{func_name} ({json.dumps(arguments)})")

        func_node : AIFunction = self.owner_env.get_ai_function(func_name)
        if func_node is None:
            result_str = f"execute {func_name} error,function not found"
        else:
            if org_msg:
                ineternal_call_record = AgentMsg.create_internal_call_msg(func_name,arguments,org_msg.get_msg_id(),org_msg.target)

            try:
                result_str:str = await func_node.execute(**arguments)
            except Exception as e:
                result_str = f"execute {func_name} error:{str(e)}"
                logger.error(f"llm execute inner func:{func_name} error:{e}")


        logger.info("llm execute inner func result:" + result_str)
        
        prompt.messages.append({"role":"function","content":result_str,"name":func_name})
        task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,self.llm_model_name,self.max_token_size,inner_functions)
        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"llm compute error:{task_result.error_str}")
            return task_result
        
        ineternal_call_record.result_str = task_result.result_str
        ineternal_call_record.done_time = time.time()
        if org_msg:
            org_msg.inner_call_chain.append(ineternal_call_record)

        inner_func_call_node = None
        if stack_limit > 0:
            result_message : dict = task_result.result.get("message")
            if result_message:
                inner_func_call_node = result_message.get("function_call")

        if inner_func_call_node:
            return await self._execute_func(inner_func_call_node,prompt,org_msg,stack_limit-1)
        else:
            return task_result
        
    async def _get_agent_prompt(self) -> AgentPrompt:
        return self.agent_prompt
    
    async def _get_agent_think_prompt(self) -> AgentPrompt:
        return self.agent_think_prompt

    def _format_msg_by_env_value(self,prompt:AgentPrompt):
        if self.owner_env is None:
            return

        for msg in prompt.messages:
            old_content = msg.get("content")
            msg["content"] = old_content.format_map(self.owner_env)

    async def _handle_event(self,event):
        if event.type == "AgentThink":
            return await self._do_think()
        

    async def _do_think(self):
        #1) load all sessions
        session_id_list = AIChatSession.list_session(self.agent_id,self.chat_db)
        #2) get history from session in token limit
        for session_id in session_id_list:
            await self.think_chatsession(session_id)

        #4) advanced: reload all chatrecord,and think the topic of message.
        #5)     some topic could be end(not be thinked in futured )
        return 
    
        
    async def think_chatsession(self,session_id):
        if self.agent_think_prompt is None:
            return
        logger.info(f"agent {self.agent_id} think session {session_id}")
        chatsession = AIChatSession.get_session_by_id(session_id,self.chat_db)

        while True:
            cur_pos = chatsession.summarize_pos
            summary = chatsession.summary
            prompt:AgentPrompt = AgentPrompt()
            #prompt.append(self._get_agent_prompt())
            prompt.append(await self._get_agent_think_prompt())
            system_prompt_len = prompt.get_prompt_token_len()
            #think env?
            history_prompt,next_pos = await self._get_history_prompt_for_think(chatsession,summary,system_prompt_len,cur_pos)
            prompt.append(history_prompt)
            is_finish = next_pos - cur_pos < 2
            if is_finish:
                logger.info(f"agent {self.agent_id} think session {session_id} is finished!,no more history")
                break
            #3) llm summarize chat history
            task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,self.llm_model_name,self.max_token_size,None)
            if task_result.result_code != ComputeTaskResultCode.OK:
                logger.error(f"llm compute error:{task_result.error_str}")
                break
            else:
                new_summary= task_result.result_str
                logger.info(f"agent {self.agent_id} think session {session_id} from {cur_pos} to {next_pos} summary:{new_summary}")
                chatsession.update_think_progress(next_pos,new_summary)
            

        
        return 

    async def _process_group_chat_msg(self,msg:AgentMsg) -> AgentMsg:  
        session_topic = msg.target + "#" + msg.topic
        chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.chat_db)
        need_process = False
        if msg.mentions is not None:
            if self.agent_id in msg.mentions:
                need_process = True
                logger.info(f"agent {self.agent_id} recv a group chat message from {msg.sender},but is not mentioned,ignore!")

        if need_process is not True:
            chatsession.append(msg)
            resp_msg = msg.create_group_resp_msg(self.agent_id,"")
            return resp_msg
        else:
            msg_prompt = AgentPrompt()
            msg_prompt.messages = [{"role":"user","content":f"{msg.sender}:{msg.body}"}]

            prompt = AgentPrompt()
            prompt.append(await self._get_agent_prompt())
            self._format_msg_by_env_value(prompt)
            inner_functions,function_token_len = self._get_inner_functions()
       
            system_prompt_len = prompt.get_prompt_token_len()
            input_len = len(msg.body)

            history_prmpt,history_token_len = await self._get_prompt_from_session_for_groupchat(chatsession,system_prompt_len + function_token_len,input_len)
            prompt.append(history_prmpt) # chat context
            prompt.append(msg_prompt)

            logger.debug(f"Agent {self.agent_id} do llm token static system:{system_prompt_len},function:{function_token_len},history:{history_token_len},input:{input_len}, totoal prompt:{system_prompt_len + function_token_len + history_token_len} ")
            task_result = await self._do_llm_complection(prompt,inner_functions,msg)
            if task_result.result_code != ComputeTaskResultCode.OK:
                error_resp = msg.create_error_resp(task_result.error_str)
                return error_resp
            
            final_result = task_result.result_str
            llm_result : LLMResult = LLMResult.from_str(final_result)
            is_ignore = False
            result_prompt_str = ""
            match llm_result.state:
                case "ignore":
                    is_ignore = True
                case "waiting":
                    for sendmsg in llm_result.send_msgs:
                        target = sendmsg.target
                        sendmsg.sender = self.agent_id
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
                resp_msg = msg.create_group_resp_msg(self.agent_id,final_result)
                chatsession.append(msg)
                chatsession.append(resp_msg)

                return resp_msg

            return None

    async def _process_msg(self,msg:AgentMsg) -> AgentMsg:
            if msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
                return await self._process_group_chat_msg(msg)

            session_topic = msg.get_sender() + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.chat_db)

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
            prompt.append(msg_prompt)

            logger.debug(f"Agent {self.agent_id} do llm token static system:{system_prompt_len},function:{function_token_len},history:{history_token_len},input:{input_len}, totoal prompt:{system_prompt_len + function_token_len + history_token_len} ")
            #task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,self.llm_model_name,self.max_token_size,inner_functions)
            task_result = await self._do_llm_complection(prompt,inner_functions,msg)
            if task_result.result_code != ComputeTaskResultCode.OK:
                error_resp = msg.create_error_resp(task_result.error_str)
                return error_resp
            
            final_result = task_result.result_str

            llm_result : LLMResult = LLMResult.from_str(final_result)
            is_ignore = False
            result_prompt_str = ""
            match llm_result.state:
                case "ignore":
                    is_ignore = True
                case "waiting":
                    for sendmsg in llm_result.send_msgs:
                        sendmsg.sender = self.agent_id
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


    
    async def _get_history_prompt_for_think(self,chatsession:AIChatSession,summary:str,system_token_len:int,pos:int)->(AgentPrompt,int):
        history_len = (self.max_token_size * 0.7) - system_token_len
        
        messages = chatsession.read_history(self.history_len,pos,"natural") # read
        result_token_len = 0
        result_prompt = AgentPrompt()
        have_summary = False
        if summary is not None:
            if len(summary) > 1:
                have_summary = True
        
        if have_summary:
                result_prompt.messages.append({"role":"user","content":summary})
                result_token_len -= len(summary)
        else:
            result_prompt.messages.append({"role":"user","content":"There is no summary yet."})
            result_token_len -= 6

        read_history_msg = 0
        history_str : str = ""
        for msg in messages:
            read_history_msg += 1
            dt = datetime.datetime.fromtimestamp(float(msg.create_time))
            formatted_time = dt.strftime('%y-%m-%d %H:%M:%S')
            record_str = f"{msg.sender},[{formatted_time}]\n{msg.body}\n"
            history_str = history_str + record_str

            history_len -= len(msg.body)
            result_token_len += len(msg.body)
            if history_len < 0:
                logger.warning(f"_get_prompt_from_session reach limit of token,just read {read_history_msg} history message.")
                break
        
        result_prompt.messages.append({"role":"user","content":history_str})
        return result_prompt,pos+read_history_msg
    
    async def _get_prompt_from_session_for_groupchat(self,chatsession:AIChatSession,system_token_len,input_token_len,is_groupchat=False):
        history_len = (self.max_token_size * 0.7) - system_token_len - input_token_len
        messages = chatsession.read_history(self.history_len) # read
        result_token_len = 0
        result_prompt = AgentPrompt()
        read_history_msg = 0
        for msg in reversed(messages):
            read_history_msg += 1
            dt = datetime.datetime.fromtimestamp(float(msg.create_time))
            formatted_time = dt.strftime('%y-%m-%d %H:%M:%S')

            if msg.sender == self.agent_id:
                if self.enable_timestamp:
                    result_prompt.messages.append({"role":"assistant","content":f"(create on {formatted_time}) {msg.body} "})
                else:
                    result_prompt.messages.append({"role":"assistant","content":msg.body})
                
            else:
                if self.enable_timestamp:
                    result_prompt.messages.append({"role":"user","content":f"(create on {formatted_time}) {msg.body} "})
                else:
                    result_prompt.messages.append({"role":"user","content":f"{msg.sender}:{msg.body}"})

            history_len -= len(msg.body)
            result_token_len += len(msg.body)
            if history_len < 0:
                logger.warning(f"_get_prompt_from_session reach limit of token,just read {read_history_msg} history message.")
                break

        return result_prompt,result_token_len

    async def _do_llm_complection(self,prompt:AgentPrompt,inner_functions:dict,org_msg:AgentMsg=None) -> ComputeTaskResult:
        from .compute_kernel import ComputeKernel
        #logger.debug(f"Agent {self.agent_id} do llm token static system:{system_prompt_len},function:{function_token_len},history:{history_token_len},input:{input_len}, totoal prompt:{system_prompt_len + function_token_len + history_token_len} ")
        task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,self.llm_model_name,self.max_token_size,inner_functions)
        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"llm compute error:{task_result.error_str}")
            #error_resp = msg.create_error_resp(task_result.error_str)
            return task_result

        result_message = task_result.result.get("message")
        inner_func_call_node = None
        if result_message:
            inner_func_call_node = result_message.get("function_call")

        if inner_func_call_node:
            call_prompt : AgentPrompt = copy.deepcopy(prompt)
            task_result = await self._execute_func(inner_func_call_node,call_prompt,inner_functions,org_msg)
            
        return task_result

    def parser_learn_llm_result(self,llm_result:str):
        pass

    async def _llm_read_article(self,item:KnowledgeObject) -> ComputeTaskResult:
        full_content = item.get_article_full_content()
        full_content_len = ComputeKernel.llm_num_tokens_from_text(full_content,self.get_llm_model_name())
        if full_content_len < self.get_llm_learn_token_limit():
            
            # 短文章不用总结catelog
            #path_list,summary = llm_get_summary(summary,full_content)
            prompt = self.get_agent_role_prompt()
            learn_prompt = self.get_learn_prompt()
            cotent_prompt = AgentPrompt(full_content)
            prompt.append(learn_prompt)
            prompt.append(cotent_prompt)
            
            env_functions = self._get_inner_functions()
            
            task_result:ComputeTaskResult = await self._do_llm_complection(prompt,env_functions)
            if task_result.result_code != ComputeTaskResultCode.OK:
                return task_result
            path_list,summary = self.parser_learn_llm_result(task_result.result_str)

        else:
            # 用传统方法对文章进行一些处理，目的是尽可能减少LLM调用的次数
            catelog = item.get_articl_catelog()
            chunk_content = full_content.read(self.get_llm_learn_token_limit())
            summary = kb.try_get_summary(catelog,full_content)
        
            while chunk_content is not None:
                #path_list,summarycatelog = llm_get_summary(summary,chunk_content)
                #learn_prompt = self.get_learn_prompt_with_summary()

                prompt = AgentPrompt("summary")
                learn_prompt.append(prompt)
                prompt = AgentPrompt(chunk_content)
                learn_prompt.append(prompt)
                
                #llm_result = self.do_llm_competion(learn_prompt)
                #path_list,summary,catelog = parser_learn_llm_result(llm_result)

                #chunk_content = full_content.read(self.get_llm_learn_token_limit())
            
        kb.insert_item(path_list,item,catelog,summary) 



    async def _get_prompt_from_session(self,chatsession:AIChatSession,system_token_len,input_token_len) -> AgentPrompt:
        # TODO: get prompt from group chat is different from single chat
        
        history_len = (self.max_token_size * 0.7) - system_token_len - input_token_len
        messages = chatsession.read_history(self.history_len) # read
        result_token_len = 0
        result_prompt = AgentPrompt()
        read_history_msg = 0

        if chatsession.summary is not None:
            if len(chatsession.summary) > 1:  
                result_prompt.messages.append({"role":"user","content":chatsession.summary})
                result_token_len -= len(chatsession.summary)

        for msg in reversed(messages):
            read_history_msg += 1
            dt = datetime.datetime.fromtimestamp(float(msg.create_time))
            formatted_time = dt.strftime('%y-%m-%d %H:%M:%S')

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

