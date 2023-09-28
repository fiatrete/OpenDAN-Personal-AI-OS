
import json
import logging
import requests
from typing import Optional, List
from pydantic import BaseModel
from llama_cpp import Llama

from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType
from .queue_compute_node import Queue_ComputeNode

logger = logging.getLogger(__name__)

"""
This is a custom implementation, it should be redesigned.
"""

class LocalLlama_ComputeNode(Queue_ComputeNode):
    def __init__(self, model_path: str, model_name: str):
        super().__init__()
        self.model_path = model_path
        self.model_name = model_name
        self.llm = Llama(model_path=model_path)

    async def execute_task(self, task: ComputeTask) -> ComputeTaskResult:
        match task.task_type:
            case ComputeTaskType.TEXT_EMBEDDING:
                model_name = task.params["model_name"]
                input = task.params["input"]
                logger.info(f"call openai {model_name} input: {input}")

                embedding = self.llm.embed(input=input)
                
                logger.info(f"local-llama({self.model_path}) response: {resp}")

                result = ComputeTaskResult()    
                result.set_from_task(task)
                result.result = embedding

                return result
            case ComputeTaskType.LLM_COMPLETION:
                mode_name = task.params["model_name"]
                prompts = task.params["prompts"]
                max_token_size = task.params.get("max_token_size")
                llm_inner_functions = task.params.get("inner_functions")
                if max_token_size is None:
                    max_token_size = 4000
                    
                logger.info(f"local-llama({self.model_path}) prompts: {prompts}")

                resp = self.llm.create_chat_completion(model=mode_name,
                                                messages=prompts,
                                                functions=llm_inner_functions, # function has not support?
                                                max_tokens=max_token_size,
                                                temperature=0.7) # TODO: add temperature to task params?

            
                logger.info(f"local-llama({self.model_path}) response: {json.dumps(resp, indent=4)}")

                result = ComputeTaskResult()
                result.set_from_task(task)

                status_code = resp["choices"][0]["finish_reason"]
                match status_code:
                    case "function_call":
                        task.state = ComputeTaskState.DONE
                    case "stop":
                        task.state = ComputeTaskState.DONE
                    case _:
                        task.state = ComputeTaskState.ERROR
                        task.error_str = f"The status code was {status_code}."
                        return None

                result.result_str = resp["choices"][0]["message"]["content"]
                result.result_message = resp["choices"][0]["message"]
                return result

    async def initial(self) -> bool:
        return True

    def display(self) -> str:
        return f"LocalLlama_ComputeNode: {self.node_id}"

    def get_capacity(self):
        pass

    def is_support(self, task: ComputeTask) -> bool:
        return (task.task_type == ComputeTaskType.TEXT_EMBEDDING or task.task_type == ComputeTaskType.LLM_COMPLETION) and (not task.params["model_name"] or task.params["model_name"] == self.model_name)

    def is_local(self) -> bool:
        return True
