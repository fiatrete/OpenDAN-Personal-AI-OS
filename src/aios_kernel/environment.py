# basic environment class
# we have some built-in environment: Calender(include timer),Home(connect to IoT device in your home), ,KnwoledgeBase,FileSystem,

from abc import ABC, abstractmethod
from typing import Callable

class EnvironmentEvent(ABC):
    @abstractmethod
    def display(self) -> str:
        pass    

class Environment:
    def __init__(self) -> None:
        pass

    def get_id(self) -> str:
        pass

    def attach_event_handler(self,event_id:str,handler:Callable) -> None:
        pass

