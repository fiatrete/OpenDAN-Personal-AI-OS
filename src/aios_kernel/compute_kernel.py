from compute_node import compute_node
from abc import ABC, abstractmethod

# How to dispatch different computing tasks (some tasks may contain a large amount of state for correct execution)
# to suitable computing nodes, achieving a balance of speed, cost, and power consumption, 
# is the CORE GOAL of the entire computing task schedule system (aios_kernel).
class compute_task(ABC):
    @abstractmethod
    def display(self) -> str:    
        pass   


class compute_kernel:
    def __init__(self) -> None:
        pass

    def run(self,task:compute_task) -> None:
        # check there is compute node can support this task
        # add task to working_queue
        pass

    def start(self):
        pass

    def add_compute_node(self,node:compute_node):
        pass

    def disable_compute_node(self,):
        pass