from abc import ABC, abstractmethod


class compute_node(ABC):
    @abstractmethod
    def display(self) -> str:
        pass

class local_compute_node(compute_node):
    def display(self) -> str:
        return super().display()
    

