from abc import ABC, abstractmethod
from typing import Dict,Coroutine,Callable

class ParameterDefine:
    def __init__(self) -> None:
        self.name = None
        self.type = None
        self.description = None
        

class AIFunction:
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

class ActionItem:
    def __init__(self,name,args) -> None:
        self.name = name
        self.args = args
        self.body = None

    def append_body(self,body:str) -> None:
        if self.body is None:
            self.body = body
        else:
            self.body += body

    def dumps(self) -> str:
        pass

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
    
    def get_description(self) -> str:
        return self.description
    
    def get_parameters(self) -> Dict:
        if self.parameters is not None:
            result = {}
            result["type"] = "object"
            parm_defines = {}
            for parm,desc in self.parameters.items():
                parm_item = {}
                parm_item["type"] = "string"
                parm_item["description"] = desc
                parm_defines[parm] = parm_item
            result["properties"] = parm_defines
            return result
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

class AIOperation:
    @abstractmethod
    def get_name(self) -> str:
        """
        return the name of the operation (should be snake case)
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        return a detailed description of what the operation does
        """
        pass


    @abstractmethod
    async def execute(self, params: dict) -> str:
        """
        Execute the function and return a JSON serializable dict.
        The parameters are passed in the form of kwargs
        """
        pass

class SimpleAIOperation(AIOperation):
    def __init__(self,op:str,description:str,func_handler:Coroutine) -> None:
        self.op = op
        self.description = description
        self.func_handler = func_handler

    def get_name(self) -> str: 
        return self.op

    def get_description(self) -> str:
        return self.description
    
    async def execute(self, params: Dict) -> str:
        if self.func_handler is None:
            return "error: function not implemented"
        
        return await self.func_handler(params)
    

class AIFunctionOperation(AIOperation):
    def __init__(self, func: AIFunction) -> None:
        self.func = func
        super().__init__()

    @abstractmethod
    def get_name(self) -> str:
        return self.func.get_name()

    @abstractmethod
    def get_description(self) -> str:
        return self.func.get_description()

    @abstractmethod
    async def execute(self, params: dict) -> str:
       self.func.execute(**params)