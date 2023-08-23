from abc import ABC, abstractmethod
from .compute_kernel import ComputeTask

class ComputeNode(ABC):
    @abstractmethod
    async def push_task(self,task:ComputeTask,proiority:int = 0):
        pass
    
    async def remove_task(self,task_id:str):
        pass

    @abstractmethod
    def get_task_state(self,task_id:str):
        pass

    @abstractmethod
    def display(self) -> str:
        pass

    @abstractmethod
    def get_capacity(self):
        pass

    @abstractmethod
    def is_support(self,task_type:str) -> bool:
        pass

    @abstractmethod
    def is_local(self) -> bool:
        pass

    @abstractmethod
    def is_trusted(self) -> bool:
        return True
    
    def get_fee_type(self) -> str:
        return "free"
    
    

class LocalComputeNode(ComputeNode):
    def display(self) -> str:
        return super().display()
    
    def is_local(self) -> bool:
        return True
    

