# pylint:disable=E0402

import abc
from abc import abstractmethod

from ..proto.agent_msg import AgentMsg

class BaseAIAgent(abc.ABC):
    @abstractmethod
    def get_id(self) -> str:
        pass

    @abstractmethod
    def get_llm_model_name(self) -> str:
        pass

    @abstractmethod
    def get_max_token_size(self) -> int:
        pass

    @abstractmethod
    async def _process_msg(self,msg:AgentMsg,workspace = None) -> AgentMsg:
        pass

class CustomAIAgent(BaseAIAgent):
    def __init__(self, agent_id: str, llm_model_name: str, max_token_size: int) -> None:
        self.agent_id = agent_id
        self.llm_model_name = llm_model_name
        self.max_token_size = max_token_size

    def get_id(self) -> str:
        return self.agent_id

    def get_llm_model_name(self) -> str:
        return self.llm_model_name

    def get_max_token_size(self) -> int:
        return self.max_token_size
