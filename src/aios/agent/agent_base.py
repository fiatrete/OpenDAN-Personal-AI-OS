import abc
import copy
from abc import abstractmethod
from datetime import datetime, timedelta
import logging
from enum import Enum
import uuid
import time
import re
import shlex
import json
from typing import List, Tuple

from ..proto.ai_function import *
from ..proto.agent_msg import *
from ..proto.compute_task import *
from ..environment.environment import *


logger = logging.getLogger(__name__)





class BaseAIAgent(abc.ABC):
    @abstractmethod
    def get_id(self) -> str:
        pass

    @abstractmethod
    def get_llm_model_name(self) -> str:
        pass

    @abstractmethod
    def get_max_token_size(self) -> int:
        pass

    @abstractmethod
    async def _process_msg(self,msg:AgentMsg,workspace = None) -> AgentMsg:
        pass

    @classmethod
    def get_inner_functions(cls, env:BaseEnvironment) -> (dict,int):
        if env is None:
            return None,0

        all_inner_function = env.get_all_ai_functions()
        if all_inner_function is None:
            return None,0

        result_func = []
        result_len = 0
        for inner_func in all_inner_function:
            func_name = inner_func.get_name()
            this_func = {}
            this_func["name"] = func_name
            this_func["description"] = inner_func.get_description()
            this_func["parameters"] = inner_func.get_parameters()
            result_len += len(json.dumps(this_func)) / 4
            result_func.append(this_func)

        return result_func,result_len

    async def do_llm_complection(
        self,
        prompt:LLMPrompt,
        org_msg:AgentMsg=None,
        env:BaseEnvironment=None,
        inner_functions=None,
        is_json_resp=False,
    ) -> ComputeTaskResult:
        from ..frame.compute_kernel import ComputeKernel

        #logger.debug(f"Agent {self.agent_id} do llm token static system:{system_prompt_len},function:{function_token_len},history:{history_token_len},input:{input_len}, totoal prompt:{system_prompt_len + function_token_len + history_token_len} ")
        if inner_functions is None and env is not None:
            inner_functions,_ = BaseAIAgent.get_inner_functions(env)

        model_name = self.get_llm_model_name()
        if org_msg.is_video_msg() or org_msg.is_image_msg():
            if model_name.startswith("gpt-4"):
                model_name = "gpt-4-vision-preview"
        if is_json_resp:
            task_result: ComputeTaskResult = await (ComputeKernel.get_instance()
            .do_llm_completion(
                prompt,
                resp_mode="json",
                mode_name=model_name,
                max_token=self.get_max_token_size(),
                inner_functions=inner_functions,
                timeout=None))
        else:
            task_result: ComputeTaskResult = await (ComputeKernel.get_instance()
            .do_llm_completion(
                prompt,
                resp_mode="text",
                mode_name=model_name,
                max_token=self.get_max_token_size(),
                inner_functions=inner_functions,
                timeout=None))
        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"_do_llm_complection llm compute error:{task_result.error_str}")
            #error_resp = msg.create_error_resp(task_result.error_str)
            return task_result

        result_message = task_result.result.get("message")
        inner_func_call_node = None
        if result_message:
            inner_func_call_node = result_message.get("function_call")

        if inner_func_call_node:
            call_prompt : LLMPrompt = copy.deepcopy(prompt)
            func_msg = copy.deepcopy(result_message)
            del func_msg["tool_calls"]
            call_prompt.messages.append(func_msg)
            task_result = await self._execute_func(env,inner_func_call_node,call_prompt,inner_functions,org_msg)

        return task_result

    async def _execute_func(
        self,
        env: BaseEnvironment,
        inner_func_call_node: dict,
        prompt: LLMPrompt,
        inner_functions: dict,
        org_msg:AgentMsg,
        stack_limit = 5
    ) -> ComputeTaskResult:
        from ..frame.compute_kernel import ComputeKernel
        arguments = None
        try:
            func_name = inner_func_call_node.get("name")
            arguments = json.loads(inner_func_call_node.get("arguments"))
            logger.info(f"llm execute inner func:{func_name} ({json.dumps(arguments)})")

            func_node : AIFunction = env.get_ai_function(func_name)
            if func_node is None:
                result_str = f"execute {func_name} error,function not found"
            else:
                result_str:str = await func_node.execute(**arguments)
        except Exception as e:
            result_str = f"execute {func_name} error:{str(e)}"
            logger.error(f"llm execute inner func:{func_name} error:{e}")


        logger.info("llm execute inner func result:" + result_str)

        prompt.messages.append({"role":"function","content":result_str,"name":func_name})
        task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,mode_name=self.get_llm_model_name(),max_token=self.get_max_token_size(),inner_functions=inner_functions)
        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"llm compute error:{task_result.error_str}")
            return task_result

        if org_msg:
            internal_call_record = AgentMsg.create_internal_call_msg(func_name,arguments,org_msg.get_msg_id(),org_msg.target)
            internal_call_record.result_str = task_result.result_str
            internal_call_record.done_time = time.time()
            org_msg.inner_call_chain.append(internal_call_record)

        inner_func_call_node = None
        if stack_limit > 0:
            result_message : dict = task_result.result.get("message")
            if result_message:
                inner_func_call_node = result_message.get("function_call")
                if inner_func_call_node:
                    func_msg = copy.deepcopy(result_message)
                    del func_msg["tool_calls"]
                    prompt.messages.append(func_msg)

        if inner_func_call_node:
            return await self._execute_func(env,inner_func_call_node,prompt,inner_functions,org_msg,stack_limit-1)
        else:
            return task_result


class CustomAIAgent(BaseAIAgent):
    def __init__(self, agent_id: str, llm_model_name: str, max_token_size: int) -> None:
        self.agent_id = agent_id
        self.llm_model_name = llm_model_name
        self.max_token_size = max_token_size

    def get_id(self) -> str:
        return self.agent_id

    def get_llm_model_name(self) -> str:
        return self.llm_model_name

    def get_max_token_size(self) -> int:
        return self.max_token_size
