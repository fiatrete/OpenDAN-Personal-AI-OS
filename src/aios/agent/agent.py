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
from ..proto.agent_task import AgentTaskState,AgentTask,AgentTodo, AgentTodoState
from ..proto.compute_task import *

from .agent_base import *
from .llm_process import *
from .llm_process_loader import *
from .llm_do_task import *
from .chatsession import *

from ..environment.workspace_env import WorkspaceEnvironment, TodoListType
from ..environment.environment import *
from ..storage.storage import AIStorage
from ..knowledge import *
from ..proto.compute_task import LLMPrompt,LLMResult

logger = logging.getLogger(__name__)

class AIAgentTemplete:
    def __init__(self) -> None:
        self.llm_model_name:str = "gpt-4-turbo-preview"
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

        self.base_dir = None
        #self.memory_db = None
        self.unread_msg = Queue() # msg from other agent
        self.owenr_bus = None

        self.memory : AgentMemory = None
        self.prviate_workspace : AgentWorkspace = None

        self.behaviors:Dict[str,BaseLLMProcess] = {}
        
    async def initial(self,params:Dict = None):
        self.base_dir = f"{AIStorage.get_instance().get_myai_dir()}/agent_data/{self.agent_id}"
        memory_base_dir = f"{self.base_dir}/memory"
        self.memory = AgentMemory(self.agent_id,memory_base_dir)
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

    async def _get_context_info(self) -> Dict:
        context_info = {}

        context_info["location"] = "SanJose"
        context_info["now"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        context_info["weather"] = "Partly Cloudy, 60°F"
        context_info["owner"] = AIStorage.get_instance().get_user_config().get_value("username")

        return context_info
    
    async def llm_process_msg(self,msg:AgentMsg) -> AgentMsg:
        need_process:bool = True
        if msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
            need_process = False
           
            session_topic = msg.target + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.memory.memory_db)
            if msg.mentions is not None:
                if self.agent_id in msg.mentions:
                    need_process = True
                    logger.info(f"agent {self.agent_id} recv a group chat message from {msg.sender},but is not mentioned,ignore!")

            if need_process is not True:
                chatsession.append(msg)
                resp_msg = msg.create_group_resp_msg(self.agent_id,"")
                return resp_msg
        
        context_info = await self._get_context_info()
        input_parms = {
            "msg":msg,
            "context_info":context_info
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
        return await self.llm_process_msg(msg)


    async def llm_self_think(self):
        llm_process : BaseLLMProcess = self.behaviors.get("self_thinking")
        if llm_process:
            logger.info(f"agent {self.agent_id} self thinking start!")

            context_info = await self._get_context_info()
            known_session_list = AIChatSession.list_session(self.agent_id,self.memory.memory_db)
            known_experience_list = await self.memory.list_experience()
            record_list = await self.memory.load_records(await self.memory.get_last_think_time())

            input_parms = {
                "record_list":record_list,
                "known_session_list":known_session_list,
                "known_experience_list":known_experience_list,
                "context_info":context_info
            }

            llm_result : LLMResult = await llm_process.process(input_parms)
            if llm_result.state == LLMResultStates.ERROR:
                logger.error(f"llm process self thinking error:{llm_result.compute_error_str}")
            elif llm_result.state == LLMResultStates.IGNORE:
                logger.info(f"llm process self thinking  ignore!")
            else:
                logger.info(f"llm process self thinking  ok!,think is:{llm_result.resp}")
                self.memory.set_last_think_time(time.time())
            self.agent_energy -= 2  
            return

    async def llm_triage_tasklist(self):
        llm_process : BaseLLMProcess = self.behaviors.get("triage_tasks")
        if llm_process:
            if self.prviate_workspace:
                filter = {}
                filter["state"] = AgentTaskState.TASK_STATE_WAIT
            
                tasklist:List[AgentTask]= await self.prviate_workspace.task_mgr.list_task(filter)


                if tasklist:
                    if len(tasklist) > 0:
                        simple_list:List[Dict] = []
                        for task in tasklist:
                            simple_list.append(task.to_simple_dict()) 
                            
                        input_parms = {
                            "tasklist":simple_list,
                            "context_info": await self._get_context_info()
                        }
                        llm_result : LLMResult = await llm_process.process(input_parms)
                        if llm_result.state == LLMResultStates.ERROR:
                            logger.error(f"llm process triage_tasks error:{llm_result.compute_error_str}")
                        elif llm_result.state == LLMResultStates.IGNORE:
                            logger.info(f"llm process triage_tasks ignore!")
                        else:
                            logger.info(f"llm process triage_tasks ok!,think is:{llm_result.resp}")
                        self.agent_energy -= 3  

                    # for agent_task in tasklist:
                    #     if self.agent_energy <= 0:
                    #         break

                    #     if agent_task.state == AgentTaskState.TASK_STATE_WAIT:
                    #         input_parms = {
                    #             "task":agent_task
                    #         }
                    #         llm_result : LLMResult = await llm_process.process(input_parms)
                    #         if llm_result.state == LLMResultStates.ERROR:
                    #             logger.error(f"llm process review_task error:{llm_result.error_str}")
                    #             continue
                    #         elif llm_result.state == LLMResultStates.IGNORE:
                    #             logger.info(f"llm process review_task ignore!")
                    #             continue
                    #         else:
                    #             determine = llm_result.raw_result.get("determine")
                    #             logger.info(f"llm process review_task ok!,think is:{determine}")
                    #         self.agent_energy -= 1  

    async def llm_do_todo(self, todo: AgentTodo):
        llm_process : BaseLLMProcess = self.behaviors.get("do")
        logger.info(f"agent {self.agent_id} DO todo {todo.todo_path} start!")
        if llm_process:
            input_parms = {
                "todo":todo,
                "context_info": await self._get_context_info()
            }
            llm_result : LLMResult = await llm_process.process(input_parms)
            if llm_result.state == LLMResultStates.ERROR:
                logger.error(f"llm process do_todo error:{llm_result.compute_error_str}")
            elif llm_result.state == LLMResultStates.IGNORE:
                logger.info(f"llm process do_todo ignore!")
            else:
                logger.info(f"llm process do_todo ok!,think is:{llm_result.resp}")
            self.agent_energy -= 1

    async def llm_check_todo(self, todo: AgentTodo):
        llm_process : BaseLLMProcess = self.behaviors.get("check")
        logger.info(f"agent {self.agent_id} CHECK todo {todo.todo_path} start!")
        if llm_process:
            input_parms = {
                "todo":todo,
                "context_info": await self._get_context_info()
            }
            llm_result : LLMResult = await llm_process.process(input_parms)
            if llm_result.state == LLMResultStates.ERROR:
                logger.error(f"llm process check_todo error:{llm_result.compute_error_str}")
            elif llm_result.state == LLMResultStates.IGNORE:
                logger.info(f"llm process check_todo ignore!")
            else:
                logger.info(f"llm process check_todo ok!,think is:{llm_result.resp}")
            self.agent_energy -= 1

            return 

    async def llm_plan_task(self,task:AgentTask):
        llm_process : BaseLLMProcess = self.behaviors.get("plan_task")
        logger.info(f"agent {self.agent_id} PLAN task {task.task_path} start!")
        if llm_process:
            input_parms = {
                "task":task,
                "context_info": await self._get_context_info()
            }
            llm_result : LLMResult = await llm_process.process(input_parms)
            if llm_result.state == LLMResultStates.ERROR:
                logger.error(f"llm process plan_task error:{llm_result.compute_error_str}")
            elif llm_result.state == LLMResultStates.IGNORE:
                logger.info(f"llm process plan_task ignore!")
            else:
                logger.info(f"llm process plan_task ok!,think is:{llm_result.resp}")
            self.agent_energy -= 1

    async def llm_review_task(self,task:AgentTask):
        llm_process : BaseLLMProcess = self.behaviors.get("review_task")
        logger.info(f"agent {self.agent_id} REVIEW task {task.task_path} start!")
        if llm_process:
            input_parms = {
                "task":task,
                "context_info": await self._get_context_info()
            }
            llm_result : LLMResult = await llm_process.process(input_parms)
            if llm_result.state == LLMResultStates.ERROR:
                logger.error(f"llm process review_task error:{llm_result.compute_error_str}")
            elif llm_result.state == LLMResultStates.IGNORE:
                logger.info(f"llm process review_task ignore!")
            else:
                logger.info(f"llm process review_task ok!,think is:{llm_result.resp}")
            self.agent_energy -= 1


    async def _self_imporve(self):
        await self.llm_self_think()

    def wake_up(self) -> None:
        if self.agent_task is None:
            self.agent_task = asyncio.create_task(self._on_timer())
        else:
            logger.warning(f"agent {self.agent_id} is already wake up!")

    async def _on_timer(self):
        await asyncio.sleep(5)
        while True:   
            try:
                now = time.time()
                if self.last_recover_time is None:
                    self.last_recover_time = now
                else:
                    if now - self.last_recover_time > 60:
                        self.agent_energy += (now - self.last_recover_time) / 60
                        self.last_recover_time = now
                        logger.info(f"agent {self.agent_id} recover energy to {self.agent_energy}")

                if self.agent_energy <= 1:
                    logger.info(f"agent {self.agent_id} energy is too low!, goto sleep!")
                    continue

                await self.llm_triage_tasklist()
                # Get un finished tasks
                #filter = {}
                #filter["state"] = AgentTaskState.TASK_STATE_WAIT
                filter = None
                task_list:List[AgentTask] = await self.prviate_workspace.task_mgr.list_task(filter)
                
                for task in task_list:
                    if self.agent_energy <= 0:
                        break

                    task = await self.prviate_workspace.task_mgr.get_task(task.task_id)
                    if task.can_plan():
                        # PLAN Task
                        await self.llm_plan_task(task)
                        task = await self.prviate_workspace.task_mgr.get_task(task.task_id)

                    if task.state == AgentTaskState.TASK_STATE_DOING:
                        # DO or Check Todo
                        can_review = False
                        todolist = await self.prviate_workspace.task_mgr.get_sub_todos(task.task_id)
                        for todo in todolist:
                            if self.agent_energy <= 0:
                                break
                            task = await self.prviate_workspace.task_mgr.get_task(task.task_id)
                            todo = await self.prviate_workspace.task_mgr.get_todo_by_id(todo.todo_id)
                            if task.state != AgentTaskState.TASK_STATE_DOING:
                                break
                            if todo.state == AgentTodoState.TODO_STATE_WAITING or todo.state == AgentTodoState.TODO_STATE_EXEC_FAILED:
                                await self.llm_do_todo(todo)
                                task = await self.prviate_workspace.task_mgr.get_task(task.task_id)
                                todo = await self.prviate_workspace.task_mgr.get_todo_by_id(todo.todo_id)
                                if task.state != AgentTaskState.TASK_STATE_DOING:
                                    break
                            if todo.state == AgentTodoState.TODO_STATE_EXEC_OK:
                                await self.llm_check_todo(todo)

                        if can_review:
                            task.state = AgentTaskState.TASK_STATE_WAITING_REVIEW

                    task = await self.prviate_workspace.task_mgr.get_task(task.task_id)
                    if task.state == AgentTaskState.TASK_STATE_WAITING_REVIEW:
                        await self.llm_review_task(task)
                    
                await self._self_imporve()
                
               
                
            except Exception as e:
                tb_str = traceback.format_exc()
                logger.error(f"agent {self.agent_id} on timer error:{e},{tb_str}")
            
            # Because the LLM itself is very slow, the accuracy of the system processing task is in minutes.
            await asyncio.sleep(30) 
                






