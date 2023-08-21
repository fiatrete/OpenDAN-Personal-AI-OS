from abc import ABC, abstractmethod
from typing import Any
from .agent import agent,agent_msg

class ai_role:
    def __init__(self) -> None:
        pass

class agent_group:
    def __init__(self) -> None:
        self.roles = None
        pass

    def add_role(self,role_name:str,agent_id:str) -> None:
        pass

    def send_msg(self,role_name:str,msg:agent_msg) -> None:
        pass

    