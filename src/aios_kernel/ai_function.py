from abc import ABC, abstractmethod
from typing import Dict,Coroutine,Callable

class AIFunction:
    def __init__(self) -> None:
        self.description : str = None
    
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
        return self.description

    @abstractmethod
    def get_parameters(self) -> Dict:
        """
        Return the list of parameters to execute this function in the form of
        JSON schema as specified in the OpenAI documentation:
        https://platform.openai.com/docs/api-reference/chat/create#chat/create-parameters

        str = run_code(code:str)
        parameters = {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code which needs to be executed"
                }
            }
        }

        """
        pass
    
    @abstractmethod
    async def execute(self, **kwargs) -> str:
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

class SimpleAIFunction(AIFunction):
    def __init__(self,func_id:str,description:str,func_handler:Coroutine,parameters:Dict = None) -> None:
        self.func_id = func_id
        self.description = description
        self.func_handler = func_handler
        self.parameters = parameters

    def get_name(self) -> str: 
        return self.func_id
    
    def get_parameters(self) -> Dict:
        if self.parameters is not None:
            return self.parameters
        return {"type": "object", "properties": {}}

    async def execute(self,**kwargs) -> str:
        if self.func_handler is None:
            return "error: function not implemented"
        
        return await self.func_handler(**kwargs)

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True
    
    def is_ready_only(self) -> bool:
        return False

