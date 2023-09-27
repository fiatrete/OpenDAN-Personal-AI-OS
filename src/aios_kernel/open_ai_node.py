import openai
import os
import asyncio
from asyncio import Queue
import logging
import json

from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType,ComputeTaskResultCode
from .compute_node import ComputeNode
from .storage import AIStorage,UserConfig

logger = logging.getLogger(__name__)


class OpenAI_ComputeNode(ComputeNode):
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = OpenAI_ComputeNode()
        return cls._instance

    @classmethod
    def declare_user_config(cls):
        if os.getenv("OPENAI_API_KEY_") is None:
            user_config = AIStorage.get_instance().get_user_config()
            user_config.add_user_config("openai_api_key","openai api key",False,None)

    def __init__(self) -> None:
        super().__init__()

        self.is_start = False
        # openai.organization = "org-AoKrOtF2myemvfiFfnsSU8rF" #buckycloud
        self.openai_api_key = None
        self.node_id = "openai_node"
        self.task_queue = Queue()


    async def initial(self):
        if os.getenv("OPENAI_API_KEY") is not None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        else:
            self.openai_api_key = AIStorage.get_instance().get_user_config().get_value("openai_api_key")

        if self.openai_api_key is None:
            logger.error("openai_api_key is None!")
            return False

        openai.api_key = self.openai_api_key
        self.start()
        return True

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"openai_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        
        result = ComputeTaskResult()
        result.result_code = ComputeTaskResultCode.ERROR
        result.set_from_task(task)

        match task.task_type:
            case ComputeTaskType.TEXT_EMBEDDING:
                model_name = task.params["model_name"]
                input = task.params["input"]
                logger.info(f"call openai {model_name} input: {input}")
                try:
                    resp = openai.Embedding.create(model=model_name,
                                                input=input)
                except Exception as e:
                    logger.error(f"openai run TEXT_EMBEDDING task error: {e}")
                    task.state = ComputeTaskState.ERROR
                    task.error_str = str(e)
                    result.error_str = str(e)
                    return result
                
                # resp = {
                # "object": "list",
                # "data": [
                #     {
                #     "object": "embedding",
                #     "index": 0,
                #     "embedding": [
                #         -0.00930514745414257,
                #         0.00765434792265296,
                #         -0.007167573552578688,
                #         -0.012373941019177437,
                #         -0.04884673282504082
                #     ]}]
                # }

                logger.info(f"openai response: {resp}")
                task.state = ComputeTaskState.DONE
                result.result_code = ComputeTaskResultCode.OK
                result.worker_id = self.node_id
                result.result = resp["data"][0]["embedding"]

                return result
            case ComputeTaskType.LLM_COMPLETION:
                mode_name = task.params["model_name"]
                prompts = task.params["prompts"]
                max_token_size = task.params.get("max_token_size")
                llm_inner_functions = task.params.get("inner_functions")
                if max_token_size is None:
                    max_token_size = 4000

                result_token = max_token_size
                try:
                    if llm_inner_functions is None:
                        logger.info(f"call openai {mode_name} prompts: {prompts}")
                        resp = openai.ChatCompletion.create(model=mode_name,
                                                        messages=prompts,
                                                        #max_tokens=result_token,
                                                        temperature=0.7)
                    else:
                        logger.info(f"call openai {mode_name} prompts: {prompts} functions: {json.dumps(llm_inner_functions)}")
                        resp = openai.ChatCompletion.create(model=mode_name,
                                                            messages=prompts,
                                                            functions=llm_inner_functions,
                                                            #max_tokens=result_token,
                                                            temperature=0.7) # TODO: add temperature to task params?
                except Exception as e:
                    logger.error(f"openai run LLM_COMPLETION task error: {e}")
                    task.state = ComputeTaskState.ERROR
                    task.error_str = str(e)
                    result.error_str = str(e)
                    return result

                logger.info(f"openai response: {json.dumps(resp, indent=4)}")

                status_code = resp["choices"][0]["finish_reason"]
                token_usage = resp.get("usage")
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
                        return result

                result.result_code = ComputeTaskResultCode.OK
                result.worker_id = self.node_id
                result.result_str = resp["choices"][0]["message"]["content"]
                result.result_message = resp["choices"][0]["message"]
                if token_usage:
                    result.result_refers["token_usage"] = token_usage
                logger.info(f"openai success response: {result.result_str}")
                return result
            case _:
                task.state = ComputeTaskState.ERROR
                task.error_str = f"ComputeTask's TaskType : {task.task_type} not support!"
                result.error_str = f"ComputeTask's TaskType : {task.task_type} not support!"
                return None

    def start(self):
        if self.is_start is True:
            return
        self.is_start = True

        async def _run_task_loop():
            while True:
                task = await self.task_queue.get()
                logger.info(f"openai_node get task: {task.display()}")
                result = self._run_task(task)
                if result is not None:
                    task.state = ComputeTaskState.DONE
                    task.result = result

        asyncio.create_task(_run_task_loop())

    def display(self) -> str:
        return f"OpenAI_ComputeNode: {self.node_id}"

    def get_task_state(self, task_id: str):
        pass

    def get_capacity(self):
        pass


    def is_support(self, task: ComputeTask) -> bool:
        if task.task_type == ComputeTaskType.LLM_COMPLETION:
            if not task.params["model_name"]:
                return True
            model_name : str = task.params["model_name"]
            if model_name.startswith("gpt-"):
                return True

        if task.task_type == ComputeTaskType.TEXT_EMBEDDING:
            if task.params["model_name"] == "text-embedding-ada-002":
                return True
        return False


    def is_local(self) -> bool:
        return False
