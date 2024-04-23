# pylint:disable=E0402
from abc import ABC, abstractmethod
from typing import Dict,Coroutine,Callable,List

class ParameterDefine:
    def __init__(self,name:str,desc:str) -> None:
        self.name:str = name
        self.type:str = "string"
        self.enum:List[str] = None
        self.description = desc
        self.is_required = True

    @classmethod
    def create_parameters(cls,json_obj:dict) -> Dict[str,'ParameterDefine']:
        result = {}
        for k,v in json_obj.items():
            param = ParameterDefine(k,v)
            result[k] = param

        return result
        

class AIFunction:
    @abstractmethod
    def get_id(self) -> str:
        """
        return the id of the function (should be snake case)
        """
        pass

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

    def get_detail_description(self) -> str:
        """
        return a detailed description of what the function does
        """
        parameters = self.get_parameters()
        parameters_str = ""
        for k,v in parameters.items():
            if len(v.description) <= 0:
                parameters_str +=f"{k},"
            else:
                if v.description == k:
                    parameters_str += f"{k},"
                else:
                    if v.is_required:
                        parameters_str += f"{k}: {v.description},"
                    else:
                        parameters_str += f"{k} (Optional): {v.description},"
        if len(parameters_str) > 0:
           return f"{self.get_description()} Parameters: {parameters_str}"
        return f"f{self.get_description()}, no parameters"

    @abstractmethod
    def get_parameters(self) -> Dict[str,ParameterDefine]:
        pass

    def get_openai_parameters(self) -> Dict:
        """
        Return the list of parameters to execute this function in the form of
        JSON schema as specified in the OpenAI documentation:
        https://platform.openai.com/docs/api-reference/chat/create#chat/create-parameters

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_current_weather",
                    "description": "Get the current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA",
                            },
                            "format": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "The temperature unit to use. Infer this from the users location.",
                            },
                        },
                        "required": ["location", "format"],
                    },
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_n_day_weather_forecast",
                    "description": "Get an N-day weather forecast",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The city and state, e.g. San Francisco, CA",
                            },
                            "format": {
                                "type": "string",
                                "enum": ["celsius", "fahrenheit"],
                                "description": "The temperature unit to use. Infer this from the users location.",
                            },
                            "num_days": {
                                "type": "integer",
                                "description": "The number of days to forecast",
                            }
                        },
                        "required": ["location", "format", "num_days"]
                    },
                }
            },
        ]

        """
        parameters = self.get_parameters()
        if parameters is not None:
            result = {}
            result["type"] = "object"
            required = []
            parm_defines = {}
            for parm_name,parm in parameters.items():
                parm_item = {}
                parm_item["type"] = parm.type 
                parm_item["description"] = parm.description
                if parm.enum is not None:
                    parm_item["enum"] = parm.enum
                parm_defines[parm_name] = parm_item
                if parm.is_required:
                    required.append(parm_name)
            result["properties"] = parm_defines
            result["required"] = required
            return result
        
        return {"type": "object", "properties": {}}
    
    @abstractmethod
    async def execute(self, arguments:Dict) -> str:
        """
        Execute the function and return a JSON serializable dict by LLM
        The parameters are passed in the form of kwargs

        [{'id': 'call_fLsKR5vGllhbWxvpqsDT3jBj',
            'type': 'function',
            'function': {'name': 'get_n_day_weather_forecast',
            'arguments': '{"location": "San Francisco, CA", "format": "celsius", "num_days": 4}'}},
        {'id': 'call_CchlsGE8OE03QmeyFbg7pkDz',
        'type': 'function',
        'function': {'name': 'get_n_day_weather_forecast',
        'arguments': '{"location": "Glasgow", "format": "celsius", "num_days": 4}'}}
        ]
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

#TODO need to be upgrade
class ActionNode:
    def __init__(self,name:str,args:List[str]) -> None:
        self.name:str= name
        self.args:List[str]= args
        self.body:str = None
        self.parms : Dict = None

    def append_body(self,body:str) -> None:
        if self.body is None:
            self.body = body
        else:
            self.body += body

    def dumps(self) -> str:
        pass

    @classmethod
    def from_json(cls,json_obj:dict) -> 'ActionNode':
        args = json_obj.get("args",[])
        r = ActionNode(json_obj["name"],args)
        if json_obj.get("body"):
            r.body = json_obj["body"]
        r.parms = json_obj

        return r
    

class SimpleAIFunction(AIFunction):
    def __init__(self,func_id:str,description:str,func_handler:Coroutine,parameters:Dict[str,ParameterDefine] = None) -> None:
        self.func_id = func_id
        self.description = description
        self.func_handler = func_handler
        self.parameters:Dict[str,ParameterDefine] = parameters

    def get_id(self) -> str: 
        return self.func_id
    
    def get_name(self) -> str:
        return self.func_id.split('.')[-1].strip()
    
    def get_description(self) -> str:
        return self.description
    
    def get_parameters(self) -> Dict[str,ParameterDefine]:
        return self.parameters
    
    async def execute(self,parameters:Dict) -> str:
        if self.func_handler is None:
            return f"error: function {self.func_id} not implemented"
        
        return await self.func_handler(parameters)

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True
    
    def is_ready_only(self) -> bool:
        return False

class AIAction:
    @abstractmethod
    def get_id(self) -> str:
        """
        return the name of the operation (should be snake case)
        """
        pass

    def get_name(self)->str:
        return self.get_id().split('.')[-1].strip()
        

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

class SimpleAIAction(AIAction):
    def __init__(self,op:str,description:str,func_handler:Coroutine) -> None:
        self.op = op
        self.description = description
        self.func_handler = func_handler

    def get_id(self) -> str: 
        return self.op

    def get_description(self) -> str:
        return self.description
    
    async def execute(self, params: Dict) -> str:
        if self.func_handler is None:
            return "error: function not implemented"
        
        return await self.func_handler(params)
    

class AIFunction2Action(AIAction):
    def __init__(self, func: AIFunction) -> None:
        super().__init__()
        self.ai_func = func

    def get_id(self) -> str:
        return self.ai_func.get_id()

    def get_description(self) -> str:
        return self.ai_func.get_detail_description()

    async def execute(self, params: dict) -> str:
        return await self.ai_func.execute(params)