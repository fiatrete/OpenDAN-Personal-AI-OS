# basic environment class
# we have some built-in environment: Calender(include timer),Home(connect to IoT device in your home), ,KnwoledgeBase,FileSystem,

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional,Dict,Awaitable,List
import logging
from ..agent.ai_function import AIFunction, AIOperation


logger = logging.getLogger(__name__)


class BaseEnvironment:
    @abstractmethod
    def get_id(self) -> str:
        pass
     
    # @abstractmethod
    # #TODO: how to use env? different env has different prompt
    # def get_env_prompt(self) -> str:
    #    pass
    
    @abstractmethod
    def get_ai_function(self,func_name:str) -> AIFunction:
        pass

    @abstractmethod
    def get_all_ai_functions(self) -> List[AIFunction]:
        pass


    @abstractmethod
    def get_ai_operation(self,op_name:str) -> AIOperation:
        pass

    @abstractmethod
    def get_all_ai_operations(self) -> List[AIOperation]:
        pass

    
    
    # _all_env = {}
    # @classmethod
    # def get_env_by_id(cls,env_id:str):
    #     return cls._all_env.get(env_id)

    # @classmethod
    # def set_env_by_id(cls,id,env):
    #     assert id == env.get_id()
    #     cls._all_env[env.get_id()] = env

class SimpleEnvironment(BaseEnvironment):
    def __init__(self, env_id: str) -> None:
        self.env_id = env_id
        self.functions: Dict[str,AIFunction] = {}
        self.operations: Dict[str,AIOperation] = {}

    def get_id(self) -> str:
        return self.env_id
    
    def add_ai_function(self,func:AIFunction) -> None:
        self.functions[func.get_name()] = func

    def get_ai_function(self,func_name:str) -> AIFunction:
        func = self.functions.get(func_name)
        if func is not None:
            return func
        return None

    def get_all_ai_functions(self) -> List[AIFunction]:
        func_list = []
        func_list.extend(self.functions.values())
        return func_list
    
    def add_ai_operation(self,op:AIOperation) -> None:
        self.operations[op.get_name()] = op
    
    def get_ai_operation(self,op_name:str) -> AIOperation:
        op = self.operations.get(op_name)
        if op is not None:
            return op
        return None

    def get_all_ai_operations(self) -> List[AIOperation]:
        op_list = []
        op_list.extend(self.operations.values())
        return op_list



class CompositeEnvironment(BaseEnvironment):
    def __init__(self, env_id: str) -> None:
        self.env_id = env_id
        self.envs:Dict[str,BaseEnvironment] = {}
        self.functions: Dict[str,AIFunction] = {}
        self.operations: Dict[str,AIOperation] = {}

    def get_id(self) -> str:
        return self.env_id
    
    def add_env(self, env: BaseEnvironment) -> None:
        self.envs[env.get_id()] = env
        functions = env.get_all_ai_functions()
        for func in functions:
            self.functions[func.get_name()] = func
        operations = env.get_all_ai_operations()
        for op in operations:
            self.operations[op.get_name()] = op

    def get_ai_function(self,func_name:str) -> AIFunction:
        func = self.functions.get(func_name)
        if func is not None:
            return func
        return None

    def get_all_ai_functions(self) -> List[AIFunction]:
        func_list = []
        func_list.extend(self.functions.values())
        return func_list
    
    def get_ai_operation(self,op_name:str) -> AIOperation:
        op = self.operations.get(op_name)
        if op is not None:
            return op
        return None
    
    def get_all_ai_operations(self) -> List[AIOperation]:
        op_list = []
        op_list.extend(self.operations.values())
        return op_list