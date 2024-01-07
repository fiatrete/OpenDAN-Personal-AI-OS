from ..proto.compute_task import LLMPrompt,LLMResult,ComputeTaskResult,ComputeTaskResultCode
from ..proto.ai_function import AIFunction,AIAction,ActionNode
from ..proto.agent_msg import AgentMsg,AgentMsgType
from ..proto.agent_task import AgentTask
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
        await self._execute_actions(actions,action_params)



class AgentPlanTask(LLMAgentBaseProcess):
    def __init__(self) -> None:
        super().__init__()

        self.role_description:str = None
        self.process_description:str = None
        self.reply_format = None

        # 虽然在架构上LLM Process可以很容易的去Call另一个Process，但实际应用中还是应该慎重的保持LLM Process的简单性
        #self.do_task_llm_process : BaseLLMProcess = None

    async def initial(self,params:Dict = None) -> bool:
        self.memory = params.get("memory")
        if self.memory is None:
            logger.error(f"LLMAgeMessageProcess initial failed! memory not found")
            return False
        self.workspace = params.get("workspace")


        return True
    
    async def load_from_config(self, config: dict,is_load_default=True) -> Coroutine[Any, Any, bool]:


        if await super().load_from_config(config) is False:
            return False
        
        self.role_description = config.get("role_desc")
        if self.role_description is None:
            logger.error(f"role_description not found in config")
            return False
        
        if config.get("process_description"):
            self.process_description = config.get("process_description")
        
        if config.get("reply_format"):
            self.reply_format = config.get("reply_format")

        if config.get("context"):
            self.context = config.get("context")
    
        self.llm_context = SimpleLLMContext()
        if config.get("llm_context"):
            self.llm_context.load_from_config(config.get("llm_context"))

    async def prepare_prompt(self,input:Dict) -> LLMPrompt:
        agent_task = input.get("task")
        prompt = LLMPrompt()
        system_prompt_dict = {}
        system_prompt_dict["role_description"] = self.role_description
        system_prompt_dict["process_rule"] = self.process_description
        system_prompt_dict["reply_format"] = self.reply_format
        prompt.append_system_message(json.dumps(system_prompt_dict,ensure_ascii=False))
        prompt.append_user_message(json.dumps(agent_task.to_dict(),ensure_ascii=False))
        return prompt
        

    async def get_review_task_actions(self) -> Dict[str,Dict]:
        pass

    async def get_inner_function_for_exec(self,func_name:str) -> AIFunction:
        pass

    async def post_llm_process(self,actions:List[ActionNode]) -> bool:
        pass

class AgentReviewTask(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict):
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self) -> LLMPrompt:
        prompt = LLMPrompt()
        pass  

    async def get_inner_function_for_exec(self,func_name:str) -> AIFunction:
        pass

    async def post_llm_process(self,actions:List[ActionNode]) -> bool:
        pass


class AgentCheck(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self) -> LLMPrompt:
        prompt = LLMPrompt()
        pass  

    async def get_inner_function_for_exec(self,func_name:str) -> AIFunction:
        pass

    async def post_llm_process(self,actions:List[ActionNode]) -> bool:
        pass

class AgentDo(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict):
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self) -> LLMPrompt:
        prompt = LLMPrompt()
        pass  

    async def get_inner_function_for_exec(self,func_name:str) -> AIFunction:
        pass

    async def post_llm_process(self,actions:List[ActionNode]) -> bool:
        pass
