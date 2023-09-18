
import asyncio
from asyncio import Queue
import logging
from abc import abstractmethod

from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType
from .compute_node import ComputeNode

logger = logging.getLogger(__name__)

class Queue_ComputeNode(ComputeNode):
    def __init__(self):
        super().__init__()
        self.task_queue = Queue()

    @abstractmethod
    async def execute_task(self, task: ComputeTask) -> {
        "content": str,
        "message": str,
        "state": ComputeTaskState,
        "error": {
            "code": int,
            "message": str,
        }
    }:
        pass

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"{self.display()} push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    async def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        
        resp = await self.execute_task(task)

        result = ComputeTaskResult()
        result.set_from_task(task)

        task.state = resp["state"]

        if task.state == ComputeTaskState.ERROR:
            task.error_str = resp["error"]["message"]


        result.worker_id = self.node_id
        result.result_str = resp["content"]
        result.result_message = resp["message"]

        return result

    def start(self):
        async def _run_task_loop():
            while True:
                task = await self.task_queue.get()
                logger.info(f"{self.display()} get task: {task.display()}")
                result = await self._run_task(task)
                if result is not None:
                    task.result = result

        asyncio.create_task(_run_task_loop())


    def get_task_state(self, task_id: str):
        pass
