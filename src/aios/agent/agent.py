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
from ..proto.agent_task import AgentTaskState,AgentTask,AgentTodo,AgentTodoResult
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
from ..proto.compute_task import ComputeTaskResult,ComputeTaskResultCode,LLMPrompt,LLMResult

logger = logging.getLogger(__name__)


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

        self.memory : AgentMemory = None
        self.prviate_workspace : AgentWorkspace = None

        self.behaviors:Dict[str,BaseLLMProcess] = {}
        
        

    async def initial(self,params:Dict = None):
        self.memory = AgentMemory(self.agent_id,self.chat_db)
        self.prviate_workspace = AgentWorkspace(self.agent_id) 
        init_params = {}
        init_params["memory"] = self.memory
        init_params["workspace"] = self.prviate_workspace
        for process_name in self.behaviors.keys():
            init_result = await self.behaviors[process_name].initial(init_params)
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

        if config.get("fullname") is None:
            logger.error(f"agent {self.agent_id} fullname is None!")
            return False
        self.fullname = config["fullname"]

        if config.get("enable_thread") is not None:
            self.enable_thread = bool(config["enable_thread"])

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
        self.behaviors = {}
        behaviors = config.get("behavior")
        for process_config_name in behaviors.keys():
            process_config = behaviors[process_config_name]
            real_config = {}
            real_config.update(config)
            real_config.update(process_config)
            load_result = await LLMProcessLoader.get_instance().load_from_config(real_config)
            if load_result:
                self.behaviors[process_config_name] = load_result
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

    def get_agent_prompt(self) -> LLMPrompt:
        return self.agent_prompt



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
        msg_process = self.behaviors.get("on_message")
        llm_result : LLMResult = await msg_process.process(input_parms)
        if llm_result.state == LLMResultStates.ERROR:
            error_resp = msg.create_error_resp(llm_result.error_str)
            return error_resp
        elif llm_result.state == LLMResultStates.IGNORE:
            return None
        else: # OK
            resp_msg = llm_result.raw_result.get("_resp_msg")
            return resp_msg

    async def _process_msg(self,msg:AgentMsg,workspace = None) -> AgentMsg:
        msg.context_info = {}
        msg.context_info["location"] = "SanJose"
        msg.context_info["now"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg.context_info["weather"] = "Partly Cloudy, 60°F"
        return await self.llm_process_msg(msg)


    async def  llm_review_tasklist(self):
        llm_process : BaseLLMProcess = self.behaviors.get("review_task")
        if llm_process:
            if self.prviate_workspace:
                tasklist = await self.prviate_workspace.task_mgr.list_task()
                if tasklist:
                    for agent_task in tasklist:
                        if self.agent_energy <= 0:
                            break

                        if agent_task.state == AgentTaskState.TASK_STATE_WAIT:
                            input_parms = {
                                "task":agent_task
                            }
                            llm_result : LLMResult = await llm_process.process(input_parms)
                            if llm_result.state == LLMResultStates.ERROR:
                                logger.error(f"llm process review_task error:{llm_result.error_str}")
                                continue
                            elif llm_result.state == LLMResultStates.IGNORE:
                                logger.info(f"llm process review_task ignore!")
                                continue
                            else:
                                determine = llm_result.raw_result.get("determine")
                                logger.info(f"llm process review_task ok!,think is:{determine}")
                            self.agent_energy -= 1  



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

    #async def think_todo_log(self,todo_log:AgentWorkLog):
    #    pass



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

                await self.llm_review_tasklist()

                # complete & check todo
                #await self._llm_run_todo_list(TodoListType.TO_WORK)

                ##await self._llm_run_todo_list(TodoListType.TO_LEARN)
               
                if self.need_self_think():
                    await self.do_self_think()
                
                # review other's todo
                # self.review_other_works()
            except Exception as e:
                tb_str = traceback.format_exc()
                logger.error(f"agent {self.agent_id} on timer error:{e},{tb_str}")
                continue





