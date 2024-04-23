from .llm_process import BaseLLMProcess, AgentMessageProcess,AgentSelfThinking,AgentSelfLearning,AgentSelfImprove
from .llm_do_task import AgentTriageTaskList,AgentPlanTask,AgentReviewTask,AgentDo,AgentCheck

from typing import Awaitable, Callable, Coroutine, Dict, List, Any
import logging

logger = logging.getLogger(__name__)

class LLMProcessLoader:
    def __init__(self) -> None:
        self.loaders : Dict[str,Callable[[dict],Awaitable[BaseLLMProcess]]] = {}
        return
    
    @classmethod
    def get_instance(cls)->"LLMProcessLoader":
        if not hasattr(cls,"_instance"):
            cls._instance = LLMProcessLoader()
        return cls._instance
    
    def register_loader(self, typename:str,loader:Callable[[dict],Awaitable[BaseLLMProcess]]):
        self.loaders[typename] = loader
    
    async def load_from_config(self,config:dict) -> BaseLLMProcess:
        llm_type_name = config.get("type")
        if llm_type_name:
            loader = self.loaders.get(llm_type_name)
            if loader:
                return await loader(config)

            selected_type = globals().get(llm_type_name)   
            if selected_type:
                result : BaseLLMProcess = selected_type()
                load_result = await result.load_from_config(config)
                if load_result is False:
                    logger.warn(f"load LLMProcess {llm_type_name} from config failed! load_from_config return False")
                    return None
                else:
                    return result


        logger.warn(f"load LLMProcess {llm_type_name} from config failed! type not found")
        return None