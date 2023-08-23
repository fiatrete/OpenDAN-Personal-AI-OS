from abc import ABC, abstractmethod
from typing import Optional
import logging
import asyncio

from .agent import agent_prompt
from .compute_node import compute_node

logger = logging.getLogger(__name__)

# How to dispatch different computing tasks (some tasks may contain a large amount of state for correct execution)
# to suitable computing nodes, achieving a balance of speed, cost, and power consumption, 
# is the CORE GOAL of the entire computing task schedule system (aios_kernel).
class compute_task(ABC):
    @abstractmethod
    def display(self) -> str:    
        pass   


class compute_kernel:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(compute_kernel, cls).__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        self.task_queue = []
        self.is_start = False
        pass

    def run(self,task:compute_task) -> None:
        # check there is compute node can support this task
        if self.is_task_support(task) is False:
            logger.error(f"task {task.display()} is not support by any compute node")
            return
        # add task to working_queue
        self.task_queue.append(task)
        

    def start(self):
        if self.is_start is True:
            logger.warn("compute_kernel is already start")
            return
        
        self.is_start = True
        async def _run_task_loop():
            while True:
                task = self.task_queue.pop(0)
                c_node:compute_node= await self._schedule(task)
                c_node.push_task(task)
        
        asyncio.create_task(_run_task_loop())
        

    async def _schedule(self,task) -> compute_node:
        pass

    def add_compute_node(self,node:compute_node):
        pass

    def disable_compute_node(self,):
        pass

    def is_task_support(self,task:compute_task) -> bool:
        pass


    # friendly interface for use:
    def llm_completion(self,prompt:agent_prompt,mode_name:Optional[str] = None,max_token:int = 0) -> compute_task:
        # craete a llm_work_task ,push on queue's end
        # then task_schedule would run this task.(might schedule some work_task to another host)
        pass

    async def do_llm_completion(self,prompt:agent_prompt,mode_name:Optional[str] = None,max_token:int = 0) -> str:
        pass
    