from asyncio import Queue
import asyncio
import openai
import os
import logging

from .compute_node import ComputeNode
from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType

logger = logging.getLogger(__name__)


class WhisperComputeNode(ComputeNode):
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.is_start = False
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        if self.is_start is True:
            logger.warn("WhisperComputeNode is already start")
            return

        self.is_start = True
        self.node_id = "whisper_node"
        self.enable = True
        self.task_queue = Queue()
        self.open_api_key = None

        if self.open_api_key is None and os.getenv("OPENAI_API_KEY") is not None:
            self.open_api_key = os.getenv("OPENAI_API_KEY")

        if self.open_api_key is None:
            raise Exception("WhisperComputeNode open_api_key is None")

        self.start()

    def start(self):
        async def _run_task_loop():
            while True:
                task = await self.task_queue.get()
                try:
                    result = self._run_task(task)
                    if result is not None:
                        task.state = ComputeTaskState.DONE
                        task.result = result
                except Exception as e:
                    logger.error(f"whisper_node run task error: {e}")
                    task.state = ComputeTaskState.ERROR
                    task.result = ComputeTaskResult()
                    task.result.set_from_task(task)
                    task.result.worker_id = self.node_id
                    task.result.result_str = str(e)

        asyncio.create_task(_run_task_loop())

    def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        prompt = task.params["prompt"]
        response_format = None
        if "response_format" in task.params:
            response_format = task.params["response_format"]
        temperature = None
        if "temperature" in task.params:
            temperature = task.params["temperature"]
        language = None
        if "language" in task.params:
            language = task.params["language"]
        file = task.params["file"]

        resp = openai.Audio.transcribe("whisper-1",
                                       file,
                                       self.open_api_key,
                                       prompt=prompt,
                                       response_format=response_format,
                                       temperature=temperature,
                                       language=language)
        result = ComputeTaskResult()
        result.set_from_task(task)
        result.worker_id = self.node_id
        result.result_str = resp["text"]
        result.result = resp
        return result

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"whisper_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def get_task_state(self, task_id: str):
        pass

    def display(self) -> str:
        return f"WhisperComputeNode: {self.node_id}"

    def get_capacity(self):
        return 0

    def is_support(self, task_type: ComputeTaskType) -> bool:
        if task_type == ComputeTaskType.VOICE_2_TEXT:
            return True
        return False

    def is_local(self) -> bool:
        return False
