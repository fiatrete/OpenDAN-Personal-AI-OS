from abc import ABC, abstractmethod
from .compute_task import ComputeTask, ComputeTaskType


class ComputeNode(ABC):
    def __init__(self) -> None:
        self.node_id = "default"
        self.enable = True

    @abstractmethod
    async def push_task(self, task: ComputeTask, proiority: int = 0):
        pass

    @abstractmethod
    async def remove_task(self, task_id: str):
        pass

    @abstractmethod
    def get_task_state(self, task_id: str):
        pass

    @abstractmethod
    def display(self) -> str:
        pass

    @abstractmethod
    def get_capacity(self):
        pass

    @abstractmethod
    def is_support(self, task: ComputeTask) -> bool:
        pass

    @abstractmethod
    def is_local(self) -> bool:
        pass

    # the hit weight when select this node in schedule
    def weight(self) -> int:
        return 1
    
    def is_trusted(self) -> bool:
        return True

    def get_fee_type(self) -> str:
        return "free"

class LocalComputeNode(ComputeNode):
    def display(self) -> str:
        return super().display()

    def is_local(self) -> bool:
        return True