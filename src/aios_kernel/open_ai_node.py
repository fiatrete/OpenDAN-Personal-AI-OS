
import openai
import os
import asyncio
from asyncio import Queue
import logging

from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType
from .compute_node import ComputeNode

logger = logging.getLogger(__name__)


class OpenAI_ComputeNode(ComputeNode):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OpenAI_ComputeNode, cls).__new__(cls)
            cls._instance.is_start = False
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        if self.is_start is True:
            logger.warn("OpenAI_ComputeNode is already start")
            return

        self.is_start = True
        # openai.organization = "org-AoKrOtF2myemvfiFfnsSU8rF" #buckycloud
        self.openai_api_key = ""
        self.node_id = "openai_node"

        self.task_queue = Queue()

        if os.getenv("OPENAI_API_KEY") is not None:
            openai.api_key = os.getenv("OPENAI_API_KEY")
        else:
            openai.api_key = self.openai_api_key

        self.start()

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"openai_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        mode_name = task.params["model_name"]
        # max_token_size = task.params["max_token_size"]
        prompts = task.params["prompts"]

        logger.info(f"call openai {mode_name} prompts: {prompts}")
        resp = openai.ChatCompletion.create(model=mode_name,
                                            messages=prompts,
                                            functions=task.params["inner_functions"],
                                            max_tokens=task.params["max_token_size"],
                                            temperature=0.7) # TODO: add temperature to task params?
        
        logger.info(f"openai response: {resp}")
        
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

        result.worker_id = self.node_id
        result.result_str = resp["choices"][0]["message"]["content"]
        result.result_message = resp["choices"][0]["message"]

        return result

    def start(self):
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

    def is_support(self, task_type: ComputeTaskType) -> bool:
        return task_type == ComputeTaskType.LLM_COMPLETION

    def is_local(self) -> bool:
        return False
