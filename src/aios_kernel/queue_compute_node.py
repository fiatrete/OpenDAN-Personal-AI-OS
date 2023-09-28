
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
    async def execute_task(self, task: ComputeTask, result: ComputeTaskResult):
        pass

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"{self.display()} push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    async def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING

        result = ComputeTaskResult()
        result.result_code = ComputeTaskResultCode.ERROR
        result.set_from_task(task)
        result.worker_id = self.node_id

        await self.execute_task(task, result)
            
        return result

    def start(self):
        if self.is_start is True:
            return
        self.is_start = True

        async def _run_task_loop():
            while True:
                task = await self.task_queue.get()
                logger.info(f"openai_node get task: {task.display()}")
                await self._run_task(task)

        asyncio.create_task(_run_task_loop())


    def get_task_state(self, task_id: str):
        pass
