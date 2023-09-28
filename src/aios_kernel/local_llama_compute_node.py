
import json
import logging
import requests
from typing import Optional, List
from pydantic import BaseModel

from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskResultCode, ComputeTaskState, ComputeTaskType
from .queue_compute_node import Queue_ComputeNode
from .storage import AIStorage,UserConfig

logger = logging.getLogger(__name__)

"""
This is a custom implementation, it should be redesigned.
"""

class LocalLlama_ComputeNode(Queue_ComputeNode):
    def __init__(self, url: str, model_name: str):
        super().__init__()
        self.url = url
        self.model_name = model_name

    async def execute_task(self, task: ComputeTask)->ComputeTaskResult:
        result = ComputeTaskResult()
        result.result_code = ComputeTaskResultCode.ERROR
        result.set_from_task(task)
        result.worker_id = self.node_id
        match task.task_type:
            case ComputeTaskType.TEXT_EMBEDDING:
                model_name = task.params["model_name"]
                input = task.params["input"]
                logger.info(f"call local-llama ({self.url}, {self.model_name}) {model_name} input: {input}")

                self.embedding(input, result)
                
                if result.result_code == ComputeTaskResultCode.OK:
                    task.state = ComputeTaskState.DONE
                else:
                    task.state = ComputeTaskState.ERROR
                    task.error_str = result.error_str

                return result
            case ComputeTaskType.LLM_COMPLETION:
                mode_name = task.params["model_name"]
                prompts = task.params["prompts"]
                    
                logger.info(f"local-llama({self.url}, {self.model_name}) prompts: {prompts}")

                self.completion(task, result)

                if result.result_code == ComputeTaskResultCode.OK:
                    task.state = ComputeTaskState.DONE
                else:
                    task.state = ComputeTaskState.ERROR
                    task.error_str = result.error_str
                
            case _:
                task.state = ComputeTaskState.ERROR
                result.result_code = ComputeTaskResultCode.ERROR
                task.error_str = f"ComputeTask's TaskType : {task.task_type} not support!"
                result.error_str = f"ComputeTask's TaskType : {task.task_type} not support!"
                return result
        
        return result

    async def initial(self) -> bool:
        return True

    def display(self) -> str:
        return f"local-llama: {self.node_id}"

    def get_capacity(self):
        pass

    def is_support(self, task: ComputeTask) -> bool:
        return (task.task_type == ComputeTaskType.TEXT_EMBEDDING or task.task_type == ComputeTaskType.LLM_COMPLETION) and (not task.params["model_name"] or task.params["model_name"] == self.model_name)

    def is_local(self) -> bool:
        return True

    def embedding(self, input: str, result: ComputeTaskResult):
        body = {
            "input": input
        }
        
        try:
            response = requests.post(self.url + "/v1/embeddings", json = body, verify=False, headers={"Content-Type": "application/json"})
            response.close()

            logger.info(f"local-llama({self.url}, {self.model_name}) task responsed, request: {body}, status-code: {response.status_code}, headers: {response.headers}, content: {response.content}")

            if response.status_code == 200:
                resp = response.json()
                result.result = resp["data"][0]["embedding"]
            elif response.status_code == 422:
                resp = response.json()
                result.result_code = ComputeTaskResultCode.ERROR
                result.error_str = "http request failed: " + str(resp["detail"][0]["msg"])
            else:
                result.result_code = ComputeTaskResultCode.ERROR
                result.error_str = "http request failed: " + str(response.status_code)
        except Exception as e:
            logger.error(f"call local-llama({self.url}, {self.model_name}) run TEXT_EMBEDDING task error: {e}")
            result.result_code = ComputeTaskResultCode.ERROR
            result.error_str = str(e)
            return result
        
    def completion(self, task: ComputeTask, result: ComputeTaskResult):
        mode_name = task.params["model_name"]
        prompts = task.params["prompts"]
        max_token_size = task.params.get("max_token_size")
        llm_inner_functions = task.params.get("inner_functions")
        if max_token_size is None:
            max_token_size = max_token_size
            
        body = {
            "messages": [],
            "max_tokens": 4000
        }

        for prompt in prompts:
            body["messages"].append({
                "role": prompt["role"],
                "content": prompt["content"]
            })
        
        try:
            response = requests.post(self.url + "/v1/chat/completions", json = body, verify=False, headers={"Content-Type": "application/json"})
            response.close()

            logger.info(f"local-llama({self.url}, {self.model_name}) task responsed, request: {body}, status-code: {response.status_code}, headers: {response.headers}, content: {response.content}")

            if response.status_code == 200:
                resp = response.json()

                status_code = resp["choices"][0]["finish_reason"]
                token_usage = resp["usage"]

                match status_code:
                    case "function_call":
                        task.state = ComputeTaskState.DONE
                    case "stop":
                        task.state = ComputeTaskState.DONE
                    case _:
                        task.state = ComputeTaskState.ERROR
                        task.error_str = f"The status code was {status_code}."
                        result.error_str = f"The status code was {status_code}."
                        result.result_code = ComputeTaskResultCode.ERROR
                        return None
                    
                result.result_code = ComputeTaskResultCode.OK
                result.result_str = resp["choices"][0]["message"]["content"]
                result.result["message"] = resp["choices"][0]["message"]
               
                if token_usage:
                    result.result_refers["token_usage"] = token_usage

                logger.info(f"local-llama({self.url}, {self.model_name}) success response: {result.result_str}")
            elif response.status_code == 422:
                resp = response.json()
                result.result_code = ComputeTaskResultCode.ERROR
                result.error_str = "http request failed: " + str(resp["detail"][0]["msg"])
            else:
                result.result_code = ComputeTaskResultCode.ERROR
                result.error_str = "http request failed: " + str(response.status_code)
        except Exception as e:
            logger.error(f"call local-llama({self.url}, {self.model_name}) run LLM_COMPLETION task error: {e}")
            result.result_code = ComputeTaskResultCode.ERROR
            result.error_str = str(e)
            return result