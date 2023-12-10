import traceback
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
import sys

from ..proto.agent_msg import AgentMsg
from ..proto.ai_function import *
from ..proto.agent_task import *
from ..proto.compute_task import *

from .agent_base import *
from .llm_process import *
from .chatsession import *
from ..environment.workspace_env import WorkspaceEnvironment, TodoListType

from ..frame.contact_manager import ContactManager,Contact,FamilyMember
from ..frame.compute_kernel import ComputeKernel
from ..frame.bus import AIBus
from ..environment.environment import *
from ..environment.workspace_env import WorkspaceEnvironment
from ..storage.storage import AIStorage

from ..knowledge import *
from ..utils import video_utils, image_utils
from ..proto.compute_task import ComputeTaskResult,ComputeTaskResultCode

logger = logging.getLogger(__name__)


# DEFAULT_AGENT_READ_REPORT_PROMPT = """
# """

# DEFAULT_AGENT_DO_PROMPT = """
# You are a helpful AI assistant.
# Solve tasks using your coding and language skills.
# In the following cases, suggest python code (in a python coding block) for the user to execute.
#     1. When you need to collect info, use the code to output the info you need, for example, browse or search the web, download/read a file, print the content of a webpage or a file, get the current date/time, check the operating system. After sufficient info is printed and the task is ready to be solved based on your language skill, you can solve the task by yourself.
#     2. When you need to perform some task with code, use the code to perform the task and output the result. Finish the task smartly.
# Solve the task step by step if you need to. If a plan is not provided, explain your plan first. Be clear which step uses code, and which step uses your language skill.
# When using code, you must indicate the script type in the code block. The user cannot provide any other feedback or perform any other action beyond executing the code you suggest. The user can't modify your code. So do not suggest incomplete code which requires users to modify. Don't use a code block if it's not intended to be executed by the user.
# If you want the user to save the code in a file before executing it, put # filename: <filename> inside the code block as the first line. Don't include multiple code blocks in one response. Do not ask users to copy and paste the result. Instead, use 'print' function for the output when relevant. Check the execution result returned by the user.
# If the result indicates there is an error, fix the error and output the code again. Suggest the full code instead of partial code or code changes. If the error can't be fixed or if the task is not solved even after the code is executed successfully, analyze the problem, revisit your assumption, collect additional info you need, and think of a different approach to try.
# When you find an answer, verify the answer carefully. Include verifiable evidence in your response if possible.
# Reply "TERMINATE" in the end when everything is done.
# """

# DEFAULT_AGENT_SELF_CHECK_PROMPT = """

# """

# DEFAULT_AGENT_GOAL_TO_TODO_PROMPT = """
# 我会给你一个目标，你需要结合自己的角色思考如何将其拆解成多个TODO。请直接返回json来表达这些TODO
# """

# DEFAULT_AGENT_LEARN_LONG_CONENT_PROMPT = """
# 我给你一段内容，尝试为期建立目录。目录的标题不能超过16个字，
# 目录要指向正文的位置（用字符偏移即可），整个目录的文本长度不能超过256个字节。并用json表达这个目录
# """


class AIAgentTemplete:
    def __init__(self) -> None:
        self.llm_model_name:str = "gpt-4-0613"
        self.max_token_size:int = 0
        self.template_id:str = None
        self.introduce:str = None
        self.author:str = None
        self.prompt:LLMPrompt = None


    def load_from_config(self,config:dict) -> bool:
        if config.get("llm_model_name") is not None:
            self.llm_model_name = config["llm_model_name"]
        if config.get("max_token_size") is not None:
            self.max_token_size = config["max_token_size"]
        if config.get("template_id") is not None:
            self.template_id = config["template_id"]
        if config.get("prompt") is not None:
            self.prompt = LLMPrompt()
            if self.prompt.load_from_config(config["prompt"]) is False:
                logger.error("load prompt from config failed!")
                return False


class AIAgent(BaseAIAgent):
    def __init__(self) -> None:
        self.role_prompt:LLMPrompt = None
        self.agent_prompt:LLMPrompt = None
        self.agent_think_prompt:LLMPrompt = None
        self.llm_model_name:str = None
        self.max_token_size:int = 128000
        self.agent_energy = 15
        self.agent_task = None
        self.last_recover_time = time.time()
        self.enable_thread = False
        self.can_do_unassigned_task = True

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
        self.read_report_prompt = None

        todo_prompts = {}
        todo_prompts[TodoListType.TO_WORK] = {
            "do": None,
            "check": None,
            "review": None,
        }
        todo_prompts[TodoListType.TO_LEARN] = {
            "do": None,
            "check": None,
            "review": None,
        }
        self.todo_prompts = todo_prompts

        self.chat_db = None
        self.unread_msg = Queue() # msg from other agent
        self.owenr_bus = None
        self.enable_function_list = None

        self.llm_process:Dict[str,BaseLLMProcess] = {}
        

    async def initial(self,params:Dict = None):
        self.memory = AgentMemory(self.agent_id,self.chat_db)

        init_params = {}
        init_params["memory"] = self.memory
        for process_name in self.llm_process.keys():
            init_result = await self.llm_process[process_name].initial(init_params)
            if init_result is False:
                logger.error(f"llm process {process_name} initial failed! initial return False")
                return False
        
        self.wake_up()
        return True

    async def load_from_config(self,config:dict) -> bool:
        if config.get("instance_id") is None:
            logger.error("agent instance_id is None!")
            return False
        self.agent_id = config["instance_id"]
        self.agent_workspace = config["workspace"]

        if config.get("fullname") is None:
            logger.error(f"agent {self.agent_id} fullname is None!")
            return False
        self.fullname = config["fullname"]

        if config.get("enable_thread") is not None:
            self.enable_thread = bool(config["enable_thread"])

        if config.get("prompt") is not None:
            self.agent_prompt = LLMPrompt()
            self.agent_prompt.load_from_config(config["prompt"])

        if config.get("think_prompt") is not None:
            self.agent_think_prompt = LLMPrompt()
            self.agent_think_prompt.load_from_config(config["think_prompt"])

        def load_todo_config(todo_type:str) -> bool:
            todo_config = config.get(todo_type)
            if todo_config is not None:
                if todo_config.get("do") is not None:
                    prompt = LLMPrompt()
                    prompt.load_from_config(todo_config["do"])
                    self.todo_prompts[todo_type]["do"] = prompt
                if todo_config.get("check") is not None:
                    prompt = LLMPrompt()
                    prompt.load_from_config(todo_config["check"])
                    self.todo_prompts[todo_type]["check"] = prompt
                if todo_config.get("review_prompt") is not None:
                    prompt = LLMPrompt()
                    prompt.load_from_config(todo_config["review_prompt"])
                    self.todo_prompts[todo_type]["review"] = prompt
        
        load_todo_config(TodoListType.TO_WORK)
        load_todo_config(TodoListType.TO_LEARN)
        
        if config.get("guest_prompt") is not None:
            self.guest_prompt_str = config["guest_prompt"]

        if config.get("owner_prompt") is not None:
            self.owner_promp_str = config["owner_prompt"]

        if config.get("contact_prompt") is not None:
            self.contact_prompt_str = config["contact_prompt"]


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
 
        #load all LLMProcess
        self.llm_process = {}
        LLMProcess = config.get("LLMProcess")
        for process_config_name in LLMProcess.keys():
            process_config = LLMProcess[process_config_name]
            real_config = {}
            real_config.update(config)
            real_config.update(process_config)
            load_result = await LLMProcessLoader.get_instance().load_from_config(real_config)
            if load_result:
                self.llm_process[process_config_name] = load_result
            else:
                logger.error(f"load LLMProcess {process_config_name} failed!")
                return False

       

        return True

    def get_id(self) -> str:
        return self.agent_id

    def get_fullname(self) -> str:
        return self.fullname

    def get_template_id(self) -> str:
        return self.template_id

    def get_llm_model_name(self) -> str:
        if self.llm_model_name is None:
            return AIStorage.get_instance().get_user_config().get_value("llm_model_name")

        return self.llm_model_name

    def get_max_token_size(self) -> int:
        return self.max_token_size

    def get_agent_role_prompt(self) -> LLMPrompt:
        return self.role_prompt

    def _get_remote_user_prompt(self,remote_user:str) -> LLMPrompt:
        cm = ContactManager.get_instance()
        contact = cm.find_contact_by_name(remote_user)
        if contact is None:
            #create guest prompt
            if self.guest_prompt_str is not None:
                prompt = LLMPrompt()
                prompt.system_message = {"role":"system","content":self.guest_prompt_str}
                return prompt
            return None
        else:
            if contact.is_family_member:
                if self.owner_promp_str is not None:
                    real_str = self.owner_promp_str.format_map(contact.to_dict())
                    prompt = LLMPrompt()
                    prompt.system_message = {"role":"system","content":real_str}
                    return prompt
            else:
                if self.contact_prompt_str is not None:
                    real_str = self.contact_prompt_str.format_map(contact.to_dict())
                    prompt = LLMPrompt()
                    prompt.system_message = {"role":"system","content":real_str}
                    return prompt

        return None

    def get_agent_prompt(self) -> LLMPrompt:
        return self.agent_prompt

    async def _get_agent_think_prompt(self) -> LLMPrompt:
        return self.agent_think_prompt

    def _format_msg_by_env_value(self,prompt:LLMPrompt):
        for msg in prompt.messages:
            old_content = msg.get("content")
            msg["content"] = old_content.format_map(self.agent_workspace)

    async def _handle_event(self,event):
        if event.type == "AgentThink":
            return await self.do_self_think()

    def get_workspace_by_msg(self,msg:AgentMsg) -> WorkspaceEnvironment:
        return self.agent_workspace

    def need_session_summmary(self,msg:AgentMsg,session:AIChatSession) -> bool:
        return False

    async def _create_openai_thread(self) -> str:
        return None

    def check_and_to_base64(self, image_path: str) -> str:
        if image_utils.is_file(image_path):
            return image_utils.to_base64(image_path, (1024, 1024))
        else:
            return image_path
        
    async def llm_process_msg(self,msg:AgentMsg) -> AgentMsg:
        need_process:bool = True
        if msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
            need_process = False
           
            session_topic = msg.target + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.chat_db)
            if msg.mentions is not None:
                if self.agent_id in msg.mentions:
                    need_process = True
                    logger.info(f"agent {self.agent_id} recv a group chat message from {msg.sender},but is not mentioned,ignore!")

            if need_process is not True:
                chatsession.append(msg)
                resp_msg = msg.create_group_resp_msg(self.agent_id,"")
                return resp_msg
        
        input_parms = {
            "msg":msg
        }
        msg_process = self.llm_process.get("message")
        llm_result : LLMResult = await msg_process.process(input_parms)
        if llm_result.state == LLMResultStates.ERROR:
            error_resp = msg.create_error_resp(llm_result.error_str)
            return error_resp
        elif llm_result.state == LLMResultStates.IGNORE:
            return None
        else: # OK
            resp_msg = llm_result.raw_result.get("resp_msg")
            return resp_msg

    async def _process_msg(self,msg:AgentMsg,workspace = None) -> AgentMsg:
        msg.context_info = {}
        msg.context_info["location"] = "SanJose"
        msg.context_info["now"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg.context_info["weather"] = "Partly Cloudy, 60°F"
        return await self.llm_process_msg(msg)
        msg_prompt = LLMPrompt()
        need_process = True
        if msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
            need_process = False
           
            session_topic = msg.target + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.chat_db)

            if msg.mentions is not None:
                if self.agent_id in msg.mentions:
                    need_process = True
                    logger.info(f"agent {self.agent_id} recv a group chat message from {msg.sender},but is not mentioned,ignore!")
        else:
            if msg.is_image_msg():
                image_prompt, images = msg.get_image_body()
                if image_prompt is None:
                    msg_prompt.messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": self.check_and_to_base64(image)}} for image in images]}]
                else:
                    content = [{"type": "text", "text": image_prompt}]
                    content.extend([{"type": "image_url", "image_url": {"url": self.check_and_to_base64(image)}} for image in images])
                    msg_prompt.messages = [{"role": "user", "content": content}]
            elif msg.is_video_msg():
                video_prompt, video = msg.get_video_body()
                frames = video_utils.extract_frames(video, (1024, 1024))
                if video_prompt is None:
                    msg_prompt.messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": frame}} for frame in frames]}]
                else:
                    content = [{"type": "text", "text": video_prompt}]
                    content.extend([{"type": "image_url", "image_url": {"url": frame}} for frame in frames])
                    msg_prompt.messages = [{"role": "user", "content": content}]
            elif msg.is_audio_msg():
                audio_file = msg.body
                resp = await (ComputeKernel.get_instance().do_speech_to_text(audio_file, None, prompt=None, response_format="text"))
                if resp.result_code != ComputeTaskResultCode.OK:
                    error_resp = msg.create_error_resp(resp.error_str)
                    return error_resp
                else:
                    msg.body = resp.result_str
                    msg_prompt.messages = [{"role":"user","content":resp.result_str}]
            else:
                msg_prompt.messages = [{"role":"user","content":msg.body}]
            session_topic = msg.get_sender() + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.chat_db)
            if self.enable_thread:
                need_create_thread = False
                if chatsession.openai_thread_id is not None:
                    if len(chatsession.openai_thread_id) < 1:
                        need_create_thread = True
                else:
                    need_create_thread = True

                if need_create_thread:
                    openai_thread_id = await self._create_openai_thread()
                    if openai_thread_id is not None:
                        chatsession.update_openai_thread_id(openai_thread_id)


        workspace = self.get_workspace_by_msg(msg)

        prompt = LLMPrompt()
        if workspace:
            prompt.append(workspace.get_prompt())
            prompt.append(workspace.get_role_prompt(self.agent_id))

        prompt.append(self.get_agent_prompt())
        prompt.append(self._get_remote_user_prompt(msg.sender))
        self._format_msg_by_env_value(prompt)

        if self.need_session_summmary(msg,chatsession):
            # get relate session(todos) summary
            summary = self.llm_select_session_summary(msg,chatsession)
            prompt.append(LLMPrompt(summary))

        known_info_str = "# Known information\n"
        have_known_info = False
        todos_str,todo_count = await workspace.todo_list[TodoListType.TO_WORK].get_todo_tree()
        if todo_count > 0:
            have_known_info = True
            known_info_str += f"## todo\n{todos_str}\n"
        inner_functions,function_token_len = BaseAIAgent.get_inner_functions(self.agent_workspace)
        system_prompt_len = ComputeKernel.llm_num_tokens(prompt)
        input_len = len(msg.body)
        if msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
            history_str,history_token_len = await self._get_prompt_from_session_for_groupchat(chatsession,system_prompt_len + function_token_len,input_len)
        else:
            history_str,history_token_len = await self.get_prompt_from_session(chatsession,system_prompt_len + function_token_len,input_len)
        if history_str:
            have_known_info = True
            known_info_str += history_str

        if have_known_info:
            known_info_prompt = LLMPrompt(known_info_str)
            prompt.append(known_info_prompt) # chat context

        prompt.append(msg_prompt)


        logger.debug(f"Agent {self.agent_id} do llm token static system:{system_prompt_len},function:{function_token_len},history:{history_token_len},input:{input_len}, totoal prompt:{system_prompt_len + function_token_len + history_token_len} ")
        task_result = await self.do_llm_complection(prompt,msg, inner_functions=inner_functions)
        if task_result.result_code != ComputeTaskResultCode.OK:
            error_resp = msg.create_error_resp(task_result.error_str)
            return error_resp

        final_result = task_result.result_str
        if final_result is not None:
            llm_result : LLMResult = LLMResult.from_str(final_result)
        else:
            llm_result = LLMResult()
            llm_result.state = "ignore"

        if llm_result.resp is None:
            if llm_result.raw_resp:
                final_result = json.dumps(llm_result.raw_resp)
        else:
            final_result = llm_result.resp


        await workspace.exec_op_list(llm_result.action_list,self.agent_id)

        is_ignore = False
        result_prompt_str = ""
        match llm_result.state:
            case "ignore":
                is_ignore = True
            case "waiting": # like inner call
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
            if msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
                resp_msg = msg.create_group_resp_msg(self.agent_id,final_result)
            else:
                resp_msg = msg.create_resp_msg(final_result)
            chatsession.append(msg)
            chatsession.append(resp_msg)

            return resp_msg

        return None


    async def _get_history_prompt_for_think(self,chatsession:AIChatSession,summary:str,system_token_len:int,pos:int)->(LLMPrompt,int):
        history_len = (self.max_token_size * 0.7) - system_token_len

        messages = chatsession.read_history(self.history_len,pos,"natural") # read
        result_token_len = 0
        result_prompt = LLMPrompt()
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
        result_prompt = LLMPrompt()
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



    async def _llm_summary_work(self,workspace:WorkspaceEnvironment):
        # read report ,and update work summary of
        # build todo list from work summary and goals
        #
        report_list = self.get_unread_reports()

        for report in report_list:
            if self.agent_energy <= 0:
                break
            # merge report to work summary
            await self._llm_read_report(report,workspace)
            self.agent_energy -= 1

        if workspace.is_mgr(self.agent_id):
            # manager can do more work
            await self._llm_review_team(workspace)
            self.agent_energy -= 5
            await self._llm_review_unassigned_todos(workspace)
            self.agent_energy -= 5


    async def _llm_review_team(self,workspace:WorkspaceEnvironment):
        pass

    async def _llm_review_unassigned_todos(self,workspace:WorkspaceEnvironment):
        pass

    async def _llm_read_report(self,report:AgentReport,worksapce:WorkspaceEnvironment):
        work_summary = worksapce.get_work_summary(self.agent_id)
        prompt : LLMPrompt = LLMPrompt()
        prompt.append(self.agent_prompt)
        prompt.append(worksapce.get_role_prompt(self.agent_id))
        prompt.append(self.read_report_prompt)
        # report is a message from other agent(human) about work
        prompt.append(LLMPrompt(work_summary))
        prompt.append(LLMPrompt(report.content))

        task_result:ComputeTaskResult = await self.do_llm_complection(prompt)

        if task_result.error_str is not None:
            logger.error(f"_llm_read_report compute error:{task_result.error_str}")
            return

        worksapce.set_work_summary(self.agent_id,task_result.result_str)

    async def _llm_run_todo_list(self, todo_list_type: TodoListType):
        workspace : WorkspaceEnvironment = self.get_workspace_by_msg(None)
        logger.info(f"agent {self.agent_id} do my work start!")

        # review todolist
        #if await self.need_review_todolist():
        #    await self._llm_review_todolist(workspace)

        todo_list = workspace.todo_list[todo_list_type]
        need_todo = await todo_list.get_todo_list(self.agent_id)
        
        check_count = 0
        do_count = 0
        review_count = 0

        for todo in need_todo:
            if self.agent_energy <= 0:
                break
            
            do_prompts = self._can_do_todo(todo_list_type, todo)
            if do_prompts:
                prompt : LLMPrompt = LLMPrompt()
                prompt.append(self.agent_prompt)
                prompt.append(workspace.get_role_prompt(self.agent_id))
                prompt.append(do_prompts)
                prompt.append(todo.to_prompt())
                
                do_result : AgentTodoResult = await self._llm_do_todo(todo, prompt, workspace)
                todo.last_do_time = datetime.datetime.now().timestamp()
                todo.retry_count += 1
               
                match do_result.result_code:
                    case AgentTodoResult.TODO_RESULT_CODE_LLM_ERROR:
                        continue
                    case AgentTodoResult.TODO_RESULT_CODE_OK:
                        todo.result = do_result
                        await todo_list.update_todo(todo.todo_id,AgentTodo.TODO_STATE_WAITING_CHECK)
                    case AgentTodoResult.TODO_RESULT_CODE_EXEC_OP_ERROR:
                        await todo_list.update_todo(todo.todo_id,AgentTodo.TODO_STATE_EXEC_FAILED)

                await todo_list.append_worklog(todo,do_result)
                self.agent_energy -= 2
                do_count += 1
                
                # review_result = await self._llm_review_todo(todo,workspace)
                # todo.last_review_time = datetime.datetime.now().timestamp()
                continue

            check_prompts = self._can_check_todo(todo_list_type, todo)
            if check_prompts:
                prompt : LLMPrompt = LLMPrompt()
                prompt.append(self.agent_prompt)
                prompt.append(workspace.get_role_prompt(self.agent_id))
                prompt.append(check_prompts)

                if todo.last_check_result:
                    prompt.append(LLMPrompt(todo.last_check_result))

                prompt.append(todo.detail)
                prompt.append(todo.result)

                check_result: AgentTodoResult = await self._llm_check_todo(todo, prompt, workspace)
                todo.last_check_time = datetime.datetime.now().timestamp()

                match check_result.result_code:
                    case AgentTodoResult.TODO_RESULT_CODE_LLM_ERROR:
                        continue
                    case AgentTodoResult.TODO_RESULT_CODE_OK:
                        await todo_list.update_todo(todo.todo_id,AgentTodo.TODO_STATE_DONE)
                    case AgentTodoResult.TODO_RESULT_CODE_EXEC_OP_ERROR:
                        await todo_list.update_todo(todo.todo_id,AgentTodo.TDDO_STATE_CHECKFAILED)

                await todo_list.append_worklog(todo, check_result)
                self.agent_energy -= 1
                check_count += 1
                continue
            
            review_prompts = self._can_review_todo(todo_list_type, todo)
            if review_prompts:
                prompt.append(workspace.get_prompt())
                prompt.append(workspace.get_role_prompt(self.agent_id))
                prompt.append(review_prompts)

                todo_tree = todo_list.get_todo_tree("/")
                prompt.append(LLMPrompt(todo_tree))

                do_result : AgentTodoResult = await self._llm_review_todo(todo, prompt, workspace)
                todo.last_review_time = datetime.datetime.now().timestamp()

                match do_result.result_code:
                    case AgentTodoResult.TODO_RESULT_CODE_LLM_ERROR:
                        continue
                    case AgentTodoResult.TODO_RESULT_CODE_EXEC_OP_ERROR:
                        continue
                    case AgentTodoResult.TODO_RESULT_CODE_OK:
                        await todo_list.update_todo(todo.todo_id,AgentTodo.TODO_STATE_REVIEWED)

                await todo_list.append_worklog(todo,do_result)
                self.agent_energy -= 1
                review_count += 1
                continue

        logger.info(f"agent {self.agent_id} ,check:{check_count} todo,do:{do_count} todo.")
    
   
    def _can_review_todo(self, todo_list_type: TodoListType, todo:AgentTodo) -> LLMPrompt:
        do_prompts = self.todo_prompts[todo_list_type].get("review")
        if not do_prompts:
            return None

        if todo.can_review() is False:
            return None

        return do_prompts
        

    def _can_check_todo(self, todo_list_type: TodoListType, todo:AgentTodo) -> LLMPrompt:
        do_prompts = self.todo_prompts[todo_list_type].get("check")
        if not do_prompts:
            return None

        if todo.can_check() is False:
            return None

        if todo.checker is not None:
            if todo.checker != self.agent_id:
                return None
        else:
            if self.can_do_unassigned_task is False:
                return None
            else:
                todo.checker = self.agent_id

        return do_prompts

    def _can_do_todo(self, todo_list_type: TodoListType, todo:AgentTodo) -> LLMPrompt:
        do_prompts = self.todo_prompts[todo_list_type].get("do")
        if not do_prompts:
            return None
        
        if todo.can_do() is False:
            return None

        if todo.worker is not None:
            if todo.worker != self.agent_id:
                return None
        else:
            if self.can_do_unassigned_task is False:
                return None
            else:
                todo.worker = self.agent_id

        return do_prompts

    async def _llm_do_todo(self, todo: AgentTodo, prompt: LLMPrompt, workspace: WorkspaceEnvironment) -> AgentTodoResult:
        result = AgentTodoResult()
        
        task_result:ComputeTaskResult = await self.do_llm_complection(prompt, is_json_resp=True)
        if task_result.error_str is not None:
            logger.error(f"_llm_do compute error:{task_result.error_str}")
            result.result_code = AgentTodoResult.TODO_RESULT_CODE_LLM_ERROR
            result.error_str = task_result.error_str
            return result

        llm_result = LLMResult.from_str(task_result.result_str)
        # result_str is the explain of how to do this todo
        result.result_str = llm_result.resp
        result.op_list = llm_result.op_list
        if llm_result.post_msgs is not None:
            for msg in llm_result.post_msgs:
                msg.sender = self.agent_id
                msg.topic = f"{todo.title}##{todo.todo_id}"
                #msg.prev_msg_id = todo.todo_id
                chatsession = AIChatSession.get_session(self.agent_id,f"{msg.target}#{msg.topic}",self.chat_db)
                chatsession.append(msg)
                resp = await AIBus.get_default_bus().post_message(msg)
                logging.info(f"agent {self.agent_id} send msg to {msg.target} result:{resp}")

        result_str, have_error = await workspace.exec_op_list(llm_result.action_list, self.agent_id)
        if have_error:
            result.result_code = AgentTodoResult.TODO_RESULT_CODE_EXEC_OP_ERROR
            #result.error_str = error_str
            return result
        result.result_str = result_str
        return result

    async def _llm_check_todo(self, todo: AgentTodo, prompt: LLMPrompt, workspace: WorkspaceEnvironment) -> AgentTodoResult:
        result = AgentTodoResult()
        
        inner_functions,_ = BaseAIAgent.get_inner_functions(workspace)
        task_result:ComputeTaskResult = await self.do_llm_complection(prompt,inner_functions=inner_functions,is_json_resp=True)

        if task_result.error_str is not None:
            logger.error(f"_llm_do compute error:{task_result.error_str}")
            result.result_code = AgentTodoResult.TODO_RESULT_CODE_LLM_ERROR
            result.error_str = task_result.error_str
            return result
        result.result_str = task_result.result_str
        todo.last_check_result = task_result.result_str
        return result
    
    async def _llm_review_todo(self, todo:AgentTodo, prompt: LLMPrompt, workspace: WorkspaceEnvironment):
        inner_functions,_ = BaseAIAgent.get_inner_functions(workspace)

        task_result:ComputeTaskResult = await self.do_llm_complection(prompt,inner_functions=inner_functions)
        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"_llm_review_todos compute error:{task_result.error_str}")
            return

        return

    # async def do_blance_knowledge_base(selft):
    #     # 整理自己的知识库(让分类更平衡，更由于自己以后的工作)，并尝试更新学习目标
    #     current_path = "/"
    #     current_list = kb.get_list(current_path)
    #     self_assessment_with_goal = self.get_self_assessment_with_goal()
    #     learn_goal = {}


    #     llm_blance_knowledge_base(current_path,current_list,self_assessment_with_goal,learn_goal,learn_power)

    #     # 主动学习
    #     # 方法目前只有使用搜索引擎一种？
    #     for goal in learn_goal.items():
    #         self.llm_learn_with_search_engine(kb,goal,learn_power)
    #         if learn_power <= 0:
    #             break

    async def do_self_think(self):
        session_id_list = AIChatSession.list_session(self.agent_id,self.chat_db)
        for session_id in session_id_list:
            if self.agent_energy <= 0:
                break
            used_energy = await self.think_chatsession(session_id)
            self.agent_energy -= used_energy

        # todo_logs = await self.get_todo_logs()
        # for todo_log in todo_logs:
        #     if self.agent_energy <= 0:
        #         break
        #     used_energy = await self.think_todo_log(todo_log)
        #     self.agent_energy -= used_energy

        return

    async def think_todo_log(self,todo_log:AgentWorkLog):
        pass

    async def think_chatsession(self,session_id):
        if self.agent_think_prompt is None:
            return
        logger.info(f"agent {self.agent_id} think session {session_id}")
        chatsession = AIChatSession.get_session_by_id(session_id,self.chat_db)

        while True:
            cur_pos = chatsession.summarize_pos
            summary = chatsession.summary
            prompt:LLMPrompt = LLMPrompt()
            #prompt.append(self._get_agent_prompt())
            prompt.append(await self._get_agent_think_prompt())
            system_prompt_len = ComputeKernel.llm_num_tokens(prompt)
            #think env?
            history_prompt,next_pos = await self._get_history_prompt_for_think(chatsession,summary,system_prompt_len,cur_pos)
            prompt.append(history_prompt)
            is_finish = next_pos - cur_pos < 2
            if is_finish:
                logger.info(f"agent {self.agent_id} think session {session_id} is finished!,no more history")
                break
            #3) llm summarize chat history
            task_result:ComputeTaskResult = await self.do_llm_complection(prompt)
            if task_result.result_code != ComputeTaskResultCode.OK:
                logger.error(f"think_chatsession llm compute error:{task_result.error_str}")
                break
            else:
                new_summary= task_result.result_str
                logger.info(f"agent {self.agent_id} think session {session_id} from {cur_pos} to {next_pos} summary:{new_summary}")
                chatsession.update_think_progress(next_pos,new_summary)
        return

    async def get_prompt_from_session(self,chatsession:AIChatSession,system_token_len,input_token_len) -> LLMPrompt:
        # TODO: get prompt from group chat is different from single chat
        if self.enable_thread:
            return None

        history_len = (self.max_token_size * 0.7) - system_token_len - input_token_len
        messages = chatsession.read_history(self.history_len) # read
        result_token_len = 0

        read_history_msg = 0
        have_known_info = False

        known_info = ""
        if chatsession.summary is not None:
            if len(chatsession.summary) > 1:
                known_info += f"## Recent conversation summary \n {chatsession.summary}\n"
                result_token_len -= len(chatsession.summary)
                have_known_info = True

        histroy_str = ""
        for msg in reversed(messages):
            read_history_msg += 1
            dt = datetime.datetime.fromtimestamp(float(msg.create_time))
            formatted_time = dt.strftime('%y-%m-%d %H:%M:%S')
            record_str = f"{msg.sender},[{formatted_time}]\n{msg.body}\n"
            have_known_info = True
            histroy_str = histroy_str + record_str

            history_len -= len(msg.body)
            result_token_len += len(msg.body)
            if history_len < 0:
                logger.warning(f"_get_prompt_from_session reach limit of token,just read {read_history_msg} history message.")
                break

        known_info += f"## Recent conversation history \n {histroy_str}\n"

        if have_known_info:
            return known_info,result_token_len
        return None,0


    def need_self_think(self) -> bool:
        return False

 
    def wake_up(self) -> None:
        if self.agent_task is None:
            self.agent_task = asyncio.create_task(self._on_timer())
        else:
            logger.warning(f"agent {self.agent_id} is already wake up!")

    # agent loop
    async def _on_timer(self):
        while True:
            await asyncio.sleep(15)
            try:
                now = time.time()
                if self.last_recover_time is None:
                    self.last_recover_time = now
                else:
                    if now - self.last_recover_time > 60:
                        self.agent_energy += (now - self.last_recover_time) / 60
                        self.last_recover_time = now

                if self.agent_energy <= 1:
                    continue

                # complete & check todo
                await self._llm_run_todo_list(TodoListType.TO_WORK)

                await self._llm_run_todo_list(TodoListType.TO_LEARN)
               
                if self.need_self_think():
                    await self.do_self_think()
                
                # review other's todo
                # self.review_other_works()
            except Exception as e:
                tb_str = traceback.format_exc()
                logger.error(f"agent {self.agent_id} on timer error:{e},{tb_str}")
                continue





