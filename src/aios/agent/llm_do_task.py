from ..proto.compute_task import LLMPrompt,LLMResult,ComputeTaskResult,ComputeTaskResultCode
from ..proto.ai_function import AIFunction,AIAction,ActionNode
from ..proto.agent_msg import AgentMsg,AgentMsgType
from ..proto.agent_task import AgentTask, AgentTodo, AgentWorkLog
from ..frame.compute_kernel import ComputeKernel

from .agent_memory import AgentMemory
from .workspace import AgentWorkspace
from .llm_context import LLMProcessContext,GlobaToolsLibrary, SimpleLLMContext
from .llm_process import BaseLLMProcess,LLMAgentBaseProcess

from abc import ABC,abstractmethod
import copy
import json
import datetime
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional,Dict,Awaitable,List
from enum import Enum
import logging

logger = logging.getLogger(__name__)

#LLM Process All the unfinished tasks,will sort the priority of the task after LLM, determine the next execution time, and complete the simple task
class AgentTriageTaskList(LLMAgentBaseProcess):
    def __init__(self) -> None:
        super().__init__()
    
    
    async def load_from_config(self,config:dict) -> bool:
        if await super().load_from_config(config) is False:
            return False
         
    async def prepare_prompt(self,input:Dict) -> LLMPrompt:
        prompt = LLMPrompt()

        task_list:List[AgentTask] = input.get("tasklist")
        context_info = input.get("context_info")
        if task_list is None:
            logger.error(f"tasklist not found in input")
            return None
        
        task_dict_list = []
        for task in task_list:
            task_dict_list.append(task.to_dict())

        prompt.append_user_message(json.dumps(task_dict_list,ensure_ascii=False))

        system_prompt_dict = self.prepare_role_system_prompt(context_info)
        # May all logs is good for Agent Triage Task List?
        have_known_info = False
        known_info = {}
        working_logs = await self.memory.load_worklogs(self.memory.agent_id)
        if len(working_logs) > 0:
            have_known_info = True
            all_worklog_node = []
            for worklog in working_logs:
                workNode = {}
                dt = datetime.fromtimestamp(float(worklog.timestamp))
                workNode["timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                workNode["type"] = worklog.work_type
                workNode["content"] = worklog.content
                workNode["result"] = worklog.result
                all_worklog_node.append(workNode)
                
            known_info["worklogs"] = all_worklog_node

        if have_known_info:
            system_prompt_dict["known_info"] = known_info

        prompt.inner_functions =LLMProcessContext.aifunctions_to_inner_functions(self.llm_context.get_all_ai_functions())
        prompt.append_system_message(json.dumps(system_prompt_dict,ensure_ascii=False))
        return prompt


    async def post_llm_process(self,actions:List[ActionNode],input:Dict,llm_result:LLMResult) -> bool:
        action_params = {}
        action_params["_input"] = input
        action_params["_memory"] = self.memory
        action_params["_workspace"] = self.workspace
        action_params["_llm_result"] = llm_result
        action_params["_agentid"] = self.memory.agent_id
        action_params["_start_at"] = datetime.now()

        result_str = "OK"
        try:
            if await self._execute_actions(actions,action_params) is False:
                result_str = "execute action failed!"
        except Exception as e:
            logger.error(f"execute action failed! {e}")
            result_str = "execute action failed!,error:" + str(e)
        
        worklog = AgentWorkLog.create_by_content(self.memory.agent_id,"triage",llm_result.resp,self.memory.agent_id)
        worklog.result = result_str 
        await self.memory.append_worklog(worklog)

# LLM a Task that never been LLMed, the result of LLM Process may be adjusted, splitting subtask or do simple task as a todo directly.
class AgentPlanTask(LLMAgentBaseProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict,is_load_default=True) -> bool:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self,input:Dict) -> LLMPrompt:
        prompt = LLMPrompt()

        agent_task : AgentTask= input.get("task")
        context_info = input.get("context_info")
        if agent_task is None:
            logger.error(f"task not found in input")
            return None

        prompt.append_user_message(json.dumps(agent_task.to_dict(),ensure_ascii=False))

        system_prompt_dict = self.prepare_role_system_prompt(context_info)

        have_known_info = False
        known_info = {}
        working_logs = await self.memory.load_worklogs(None,agent_task.task_id)
        if len(working_logs) > 0:
            have_known_info = True
            all_worklog_node = []
            for worklog in working_logs:
                workNode = {}
                dt = datetime.fromtimestamp(float(worklog.timestamp))
                workNode["timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                workNode["type"] = worklog.work_type
                workNode["operator"] = worklog.operator
                workNode["content"] = worklog.content
                workNode["result"] = worklog.result
                all_worklog_node.append(workNode)
                
            known_info["worklogs"] = all_worklog_node

        if have_known_info:
            system_prompt_dict["known_info"] = known_info

        prompt.inner_functions =LLMProcessContext.aifunctions_to_inner_functions(self.llm_context.get_all_ai_functions())
        prompt.append_system_message(json.dumps(system_prompt_dict,ensure_ascii=False))
        return prompt
        

    async def post_llm_process(self,actions:List[ActionNode],input:Dict,llm_result:LLMResult) -> bool:
        action_params = {}
        action_params["_input"] = input
        agent_task : AgentTask= input.get("task")
        action_params["_memory"] = self.memory
        action_params["_workspace"] = self.workspace
        action_params["_llm_result"] = llm_result
        action_params["_agentid"] = self.memory.agent_id
        action_params["_start_at"] = datetime.now()

        result_str = "OK"
        try:
            if await self._execute_actions(actions,action_params) is False:
                result_str = "execute action failed!"
        except Exception as e:
            logger.error(f"execute action failed! {e}")
            result_str = "execute action failed!,error:" + str(e)
        
        worklog = AgentWorkLog.create_by_content(agent_task.task_id,"plan",llm_result.resp,self.memory.agent_id)
        worklog.result = result_str 
        await self.memory.append_worklog(worklog)


# Agent DO Todo 
# The purpose is to complete Todo.It is the core LLM process.  Can use sufficient external tools to do your best according to the identity and ability of AGENT.It is also the LLM Process of the main extension of Agent extension
class AgentDo(LLMAgentBaseProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict,is_load_default=True) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self,input:Dict) -> LLMPrompt:
        prompt = LLMPrompt()

        agent_todo : AgentTodo= input.get("todo")
        context_info = input.get("context_info")
        if agent_todo is None:
            logger.error(f"task not found in input")
            return None

        prompt.append_user_message(json.dumps(agent_todo.to_dict(),ensure_ascii=False))

        system_prompt_dict = self.prepare_role_system_prompt(context_info)
        # May all logs is good for Agent Triage Task List?
        have_known_info = False
        known_info = {}
        working_logs = await self.memory.load_worklogs(None,agent_todo.todo_id)
        if len(working_logs) > 0:
            have_known_info = True
            all_worklog_node = []
            for worklog in working_logs:
                workNode = {}
                dt = datetime.fromtimestamp(float(worklog.timestamp))
                workNode["timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                workNode["type"] = worklog.work_type
                workNode["content"] = worklog.content
                workNode["result"] = worklog.result
                all_worklog_node.append(workNode)
                
            known_info["worklogs"] = all_worklog_node

        if have_known_info:
            system_prompt_dict["known_info"] = known_info

        prompt.inner_functions =LLMProcessContext.aifunctions_to_inner_functions(self.llm_context.get_all_ai_functions())
        prompt.append_system_message(json.dumps(system_prompt_dict,ensure_ascii=False))
        return prompt
        

    async def post_llm_process(self,actions:List[ActionNode],input:Dict,llm_result:LLMResult) -> bool:
        action_params = {}
        action_params["_input"] = input
        agent_todo : AgentTodo= input.get("todo")
        action_params["_memory"] = self.memory
        action_params["_workspace"] = self.workspace
        action_params["_llm_result"] = llm_result
        action_params["_agentid"] = self.memory.agent_id
        action_params["_start_at"] = datetime.now()

        result_str = "OK"
        try:
            if await self._execute_actions(actions,action_params) is False:
                result_str = "execute action failed!"
        except Exception as e:
            logger.error(f"execute action failed! {e}")
            result_str = "execute action failed!,error:" + str(e)
        
        worklog = AgentWorkLog.create_by_content(agent_todo.todo_id,"do",llm_result.resp,self.memory.agent_id)
        worklog.result = result_str 
        await self.memory.append_worklog(worklog)

#Agent check todo  
# LLM a already-DO TODO, the purpose is to check whether it is completed to face the illusion of LLM.Check can use some tools, which is also the core of the agent extension。
class AgentCheck(LLMAgentBaseProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict,is_load_default=True) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self,input:Dict) -> LLMPrompt:
        prompt = LLMPrompt()

        agent_todo : AgentTodo= input.get("todo")
        context_info = input.get("context_info")
        if agent_todo is None:
            logger.error(f"task not found in input")
            return None

        prompt.append_user_message(json.dumps(agent_todo.to_dict(),ensure_ascii=False))

        system_prompt_dict = self.prepare_role_system_prompt(context_info)
        # May all logs is good for Agent Triage Task List?
        have_known_info = False
        known_info = {}
        working_logs = await self.memory.load_worklogs(None,agent_todo.todo_id)
        if len(working_logs) > 0:
            have_known_info = True
            all_worklog_node = []
            for worklog in working_logs:
                workNode = {}
                dt = datetime.fromtimestamp(float(worklog.timestamp))
                workNode["timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                workNode["type"] = worklog.work_type
                workNode["content"] = worklog.content
                workNode["result"] = worklog.result
                all_worklog_node.append(workNode)
                
            known_info["worklogs"] = all_worklog_node

        if have_known_info:
            system_prompt_dict["known_info"] = known_info

        prompt.inner_functions =LLMProcessContext.aifunctions_to_inner_functions(self.llm_context.get_all_ai_functions())
        prompt.append_system_message(json.dumps(system_prompt_dict,ensure_ascii=False))
        return prompt
        

    async def post_llm_process(self,actions:List[ActionNode],input:Dict,llm_result:LLMResult) -> bool:
        action_params = {}
        action_params["_input"] = input
        agent_todo : AgentTodo= input.get("todo")
        action_params["_memory"] = self.memory
        action_params["_workspace"] = self.workspace
        action_params["_llm_result"] = llm_result
        action_params["_agentid"] = self.memory.agent_id
        action_params["_start_at"] = datetime.now()

        result_str = "OK"
        try:
            if await self._execute_actions(actions,action_params) is False:
                result_str = "execute action failed!"
        except Exception as e:
            logger.error(f"execute action failed! {e}")
            result_str = "execute action failed!,error:" + str(e)
        
        worklog = AgentWorkLog.create_by_content(agent_todo.todo_id,"check",llm_result.resp,self.memory.agent_id)
        worklog.result = result_str 
        await self.memory.append_worklog(worklog)

#Agent review task
#When Task's Todolist is completed, or Task's subtask is completed, LLM review  a TASK to determine that the Task has been completed.This Review also failed to execute.
class AgentReviewTask(LLMAgentBaseProcess):
    def __init__(self) -> None:
        super().__init__()

    
    async def load_from_config(self, config: dict,is_load_default=True) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self,input:Dict) -> LLMPrompt:
        prompt = LLMPrompt()

        agent_task : AgentTask= input.get("task")
        context_info = input.get("context_info")
        if agent_task is None:
            logger.error(f"task not found in input")
            return None

        prompt.append_user_message(json.dumps(agent_task.to_dict(),ensure_ascii=False))

        system_prompt_dict = self.prepare_role_system_prompt(context_info)
        # May all logs is good for Agent Triage Task List?
        have_known_info = False
        known_info = {}
        working_logs = await self.memory.load_worklogs(None,agent_task.task_id)
        if len(working_logs) > 0:
            have_known_info = True
            all_worklog_node = []
            for worklog in working_logs:
                workNode = {}
                dt = datetime.fromtimestamp(float(worklog.timestamp))
                workNode["timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                workNode["type"] = worklog.work_type
                workNode["operator"] = worklog.operator
                workNode["content"] = worklog.content
                workNode["result"] = worklog.result
                all_worklog_node.append(workNode)
                
            known_info["worklogs"] = all_worklog_node

        if have_known_info:
            system_prompt_dict["known_info"] = known_info

        prompt.inner_functions =LLMProcessContext.aifunctions_to_inner_functions(self.llm_context.get_all_ai_functions())
        prompt.append_system_message(json.dumps(system_prompt_dict,ensure_ascii=False))
        return prompt
        

    async def post_llm_process(self,actions:List[ActionNode],input:Dict,llm_result:LLMResult) -> bool:
        action_params = {}
        action_params["_input"] = input
        agent_task : AgentTask= input.get("task")
        action_params["_memory"] = self.memory
        action_params["_workspace"] = self.workspace
        action_params["_llm_result"] = llm_result
        action_params["_agentid"] = self.memory.agent_id
        action_params["_start_at"] = datetime.now()

        result_str = "OK"
        try:
            if await self._execute_actions(actions,action_params) is False:
                result_str = "execute action failed!"
        except Exception as e:
            logger.error(f"execute action failed! {e}")
            result_str = "execute action failed!,error:" + str(e)
        
        worklog = AgentWorkLog.create_by_content(agent_task.task_id,"review",llm_result.resp,self.memory.agent_id)
        worklog.result = result_str 
        await self.memory.append_worklog(worklog)