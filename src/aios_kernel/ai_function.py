from abc import ABC, abstractmethod
from typing import Dict

class AIFunction:
    def __init__(self) -> None:
        self.intro : str = None
    
    @abstractmethod
    def get_name(self) -> str:
        """
        return the name of the function (should be snake case)
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        return a detailed description of what the function does
        """
        pass

    @abstractmethod
    def get_parameters(self) -> Dict:
        """
        Return the list of parameters to execute this function in the form of
        JSON schema as specified in the OpenAI documentation:
        https://platform.openai.com/docs/api-reference/chat/create#chat/create-parameters
        """
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict:
        """
        Execute the function and return a JSON serializable dict.
        The parameters are passed in the form of kwargs
        """
        pass

    @abstractmethod
    def is_local(self) -> bool:
        """
        is this function call need network?
        """
        pass

    @abstractmethod
    def is_in_zone(self) -> bool:
        """
        is this function call in Lan?
        """
        pass

    @abstractmethod  
    def is_ready_only(self) -> bool:
        pass

    #def load_from_config(self,config:dict) -> bool:
    #    pass

# call chain is a combination of ai_function,group of ai_function.
class CallChain:
    def __init__(self) -> None:
        pass

    def load_from_config(self,config:dict) -> bool:
        pass

    async def execute(self):
        pass