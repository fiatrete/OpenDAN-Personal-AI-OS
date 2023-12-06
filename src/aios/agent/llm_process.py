# Old name is behavior, I belive new name "llm_process" is better
from abc import ABC,abstractmethod
import copy
import json
import shlex
from typing import Any, Callable, Optional,Dict,Awaitable,List
from enum import Enum

from ..proto.compute_task import *
from ..proto.ai_function import *
from ..frame.compute_kernel import *

import logging
logger = logging.getLogger(__name__)

MIN_PREDICT_TOKEN_LEN = 32


class BaseLLMProcess:
    def __init__(self) -> None:
        self.enable_json_resp = False
        self.model_name = "gpt-4"
        self.max_token = 2000 # include input prompt
        self.timeout = 1800 # 30 min

    @abstractmethod
    async def prepare_prompt(self) -> LLMPrompt:
        pass

    @abstractmethod
    async def get_inner_function(self,func_name:str) -> AIFunction:
        pass

    async def _execute_inner_func(self,inner_func_call_node,prompt: LLMPrompt,stack_limit = 5) -> ComputeTaskResult:
        arguments = None
        try:
            func_name = inner_func_call_node.get("name")
            arguments = json.loads(inner_func_call_node.get("arguments"))
            logger.info(f"LLMProcess execute inner func:{func_name} :\n\t {json.dumps(arguments)}")

            func_node : AIFunction = await self.get_inner_function(func_name)
            if func_node is None:
                result_str:str = f"execute {func_name} error,function not found"
            else:
                result_str:str = await func_node.execute(**arguments)
        except Exception as e:
            result_str = f"execute {func_name} error:{str(e)}"
            logger.error(f"LLMProcess execute inner func:{func_name} error:\n\t{e}")

        logger.info("LLMProcess execute inner func result:" + result_str)

        prompt.messages.append({"role":"function","content":result_str,"name":func_name})
        if self.enable_json_resp:
            resp_mode = "json"
        else:
            resp_mode = "text"

        max_result_token = self.max_token - ComputeKernel.llm_num_tokens(prompt)
        if max_result_token < MIN_PREDICT_TOKEN_LEN:
            task_result = ComputeTaskResult()
            task_result.result_code = ComputeTaskResultCode.ERROR
            task_result.error_str = f"prompt too long,can not predict"
            return task_result
       
        task_result: ComputeTaskResult = await (ComputeKernel.get_instance().do_llm_completion(
            prompt,
            resp_mode=resp_mode,
            mode_name=self.model_name,
            max_token=max_result_token,
            inner_functions=prompt.inner_functions,
            timeout=self.timeout))

        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"llm compute error:{task_result.error_str}")
            return task_result

        inner_func_call_node = None
        if stack_limit > 0:
            result_message : dict = task_result.result.get("message")
            if result_message:
                inner_func_call_node = result_message.get("function_call")
                if inner_func_call_node:
                    func_msg = copy.deepcopy(result_message)
                    del func_msg["tool_calls"]#TODO: support tool_calls?
                    prompt.messages.append(func_msg)
        else:
            logger.error(f"inner function call stack limit reached")
            task_result.result_code = ComputeTaskResultCode.ERROR
            task_result.error_str = "inner function call stack limit reached"
            return task_result

        if inner_func_call_node:
            return await self._execute_inner_func(inner_func_call_node,prompt,stack_limit-1)
        else:
            return task_result

    async def process(self) -> LLMResult:
        if self.enable_json_resp:
            resp_mode = "json"
        else:
            resp_mode = "text"

        prompt = await self.prepare_prompt()
        max_result_token = self.max_token - ComputeKernel.llm_num_tokens(prompt)
        if max_result_token < MIN_PREDICT_TOKEN_LEN:
            return LLMResult.from_error_str(f"prompt too long,can not predict")

        task_result: ComputeTaskResult = await (ComputeKernel.get_instance().do_llm_completion(
                prompt,
                resp_mode=resp_mode,
                mode_name=self.model_name,
                max_token=max_result_token,
                inner_functions=prompt.inner_functions,
                timeout=self.timeout))
        
        if task_result.result_code != ComputeTaskResultCode.OK:
            err_str = f"do_llm_completion error:{task_result.error_str}"
            logger.error(err_str)
            return LLMResult.from_error_str(err_str)
        
        result_message = task_result.result.get("message")
        inner_func_call_node = None
        if result_message:
            inner_func_call_node = result_message.get("function_call")

        if inner_func_call_node:
            call_prompt : LLMPrompt = copy.deepcopy(prompt)
            func_msg = copy.deepcopy(result_message)
            del func_msg["tool_calls"]
            call_prompt.messages.append(func_msg)
            task_result = await self._execute_inner_func(inner_func_call_node,call_prompt)

        # parse task_result to LLM Result
        if self.enable_json_resp:
            llm_result = LLMResult.from_json_str(task_result.result_str)
        else:
            llm_result = LLMResult.from_str(task_result.result_str)

        # execute op_list in LLM Result?

        return llm_result
    
#class LLMProcess
            





