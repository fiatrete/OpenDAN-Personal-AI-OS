
import asyncio
from asyncio import Queue
import logging
from abc import abstractmethod

from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskResultCode, ComputeTaskState, ComputeTaskType
from .compute_node import ComputeNode

logger = logging.getLogger(__name__)

class Queue_ComputeNode(ComputeNode):
    def __init__(self):
        super().__init__()
        self.task_queue = Queue()
        self.is_start = False

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

        result.worker_id = self.node_id
        task.state = resp["state"]
        
        if task.state == ComputeTaskState.ERROR:
            result.result_code = ComputeTaskResultCode.ERROR
            task.error_str = resp["error"]["message"]
        else:
            result.result_code = ComputeTaskResultCode.OK
            result.result_str = resp["content"]
            result.result_message = resp["message"]

        result.set_from_task(task)

        return result

    async def start(self):
        if self.is_start is True:
            return
        self.is_start = True

        async def _run_task_loop():
            while True:
                task = await self.task_queue.get()
                logger.info(f"openai_node get task: {task.display()}")
                self._run_task(task)

        asyncio.create_task(_run_task_loop())


    def get_task_state(self, task_id: str):
        pass
