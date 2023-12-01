# basic environment class
# we have some built-in environment: Calender(include timer),Home(connect to IoT device in your home), ,KnwoledgeBase,FileSystem,

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional,Dict,Awaitable,List
import logging

from ..agent.ai_function import AIFunction

logger = logging.getLogger(__name__)

class EnvironmentEvent(ABC):
    @abstractmethod
    def display(self) -> str:
        pass

EnvironmentEventHandler = Callable[[str,EnvironmentEvent],Awaitable[Any]]

class Environment:
    _all_env = {}
    @classmethod
    def get_env_by_id(cls,env_id:str):
        return cls._all_env.get(env_id)

    @classmethod
    def set_env_by_id(cls,id,env):
        assert id == env.get_id()
        cls._all_env[env.get_id()] = env

    def __init__(self,env_id:str) -> None:
        self.env_id = env_id
        self.values:Dict[str,str] = {}
        self.get_handlers:Dict[str,Callable] = {}
        self.owner_env:Dict[str,Environment] = {}
        # self.valid_keys:Dict[str,bool] = None
        self.event_handlers:Dict[str,List[EnvironmentEventHandler]]= {}

        self.functions : Dict[str,AIFunction] = {}

    def get_id(self) -> str:
        return self.env_id

    def add_owner_env(self,env) -> None:
        self.owner_env[env.get_id()] = env

    #@abstractmethod
    #TODO: how to use env? different env has different prompt
    def get_env_prompt(self) -> str:
       pass

    def add_ai_function(self,func:AIFunction) -> None:
        if self.functions.get(func.get_name()) is not None:
            logger.warn(f"add ai_function {func.get_name()} in env {self.env_id}:function already exist")

        self.functions[func.get_name()] = func

    def get_ai_function(self,func_name:str) -> AIFunction:
        func = self.functions.get(func_name)
        if func is not None:
            return func

        for owner_env in self.owner_env.values():
            func = owner_env.get_ai_function(func_name)
            if func is not None:
                return func

        return None

    #def enable_ai_function(self,func_name:str) -> None:
    #    pass

    #def disable_ai_function(self,func_name:str) -> None:
    #    pass

    def get_all_ai_functions(self) -> List[AIFunction]:
        func_list = []
        func_list.extend(self.functions.values())
        for owner_env in self.owner_env.values():
            func_list.extend(owner_env.get_all_ai_functions())
        return func_list

    @abstractmethod
    def _do_get_value(self,key:str) -> Optional[str]:
        pass

    def register_get_handler(self,key:str,handler:Callable) -> None:
        h = self.get_handlers.get(key)
        if h is not None:
            logger.warn(f"register get_handler {key} in env {self.env_id}:handler already exist")

        self.get_handlers[key] = handler


    def attach_event_handler(self,event_id:str,handler:Callable) -> None:
        handler_list = self.event_handlers.get(event_id)
        if handler_list is None:
            handler_list = []
            self.event_handlers[event_id] = handler_list

        handler_list.append(handler)

    def remove_event_handler(self,event_id:str,handler:Callable) -> None:
        handler_list = self.event_handlers.get(event_id)
        if handler is not None:
            handler_list.remove(handler)
            return

        logger.warn(f"remove event_handler {event_id} in env {self.env_id}:handler not found")

    async def fire_event(self,event_id:str,event:EnvironmentEvent) -> None:
        handler_list = self.event_handlers.get(event_id)
        if handler_list is not None:
            for handler in handler_list:
                await handler(self.env_id,event)
        else:
            logger.debug(f"fire event {event_id} in env {self.env_id}:handler not found")
        return

    def __getitem__(self, key):
        return self.get_value(key)

    def get_value(self,key:str) -> Optional[str]:
        handler = self.get_handlers.get(key)
        if handler is not None:
            return handler()

        s = self.values.get(key)
        if isinstance(s,str):
            return s
        else:
            logger.warn(f"get value {key} in env {self.env_id} failed!,type is not str")

        s = self._do_get_value(key)
        if s is not None:
            return s
        if self.owner_env is not None:
            for env in self.owner_env.values():
                s = env.get_value(key)
                if s is not None:
                    return s

        logger.warn(f"get value {key} in env {self.env_id} failed!,not found")
        return None

    def set_value(self, key: str, str_value: str,is_storage:bool = True):
        logger.info(f"set value {key} in env {self.env_id} to {str_value}")
        self.values[key] = str_value

