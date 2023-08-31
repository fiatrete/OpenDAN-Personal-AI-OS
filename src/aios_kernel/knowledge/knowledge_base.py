# define a knowledge base class
from src.aios_kernel.agent import AgentPrompt
from .object import KnowledgeObject

class KnowledgeBase:
    async def insert(self, object: KnowledgeObject):
        pass

    async def query(self, prompt: AgentPrompt) -> AgentPrompt:
        pass

    