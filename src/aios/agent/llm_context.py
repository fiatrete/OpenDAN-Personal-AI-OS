# pylint:disable=E0402
from abc import ABC, abstractmethod 
import json
import logging
from typing import Optional,Set,List,Dict,Callable

from ..proto.ai_function import AIFunction,AIAction, AIFunction2Action,SimpleAIAction

logger = logging.getLogger(__name__)

class LLMProcessContext:
    def __init__(self) -> None:
        pass

    
    @staticmethod
    def function2action(ai_func:AIFunction) -> AIAction:
        return AIFunction2Action(ai_func)

    @staticmethod
    def aifunctions_to_inner_functions(all_inner_function:List[AIFunction]) -> List[Dict]:
        if all_inner_function is None:
            return []
        
        result_func = []
        result_len = 0
        for inner_func in all_inner_function:
            func_name = inner_func.get_name()
            this_func = {}
            this_func["name"] = func_name
            this_func["description"] = inner_func.get_description()
            this_func["parameters"] = inner_func.get_openai_parameters()
            result_len += len(json.dumps(this_func,ensure_ascii=False)) / 4
            result_func.append(this_func)
        return result_func
    
    
    @abstractmethod
    def get_ai_function(self,func_name:str) -> AIFunction:
        pass

    def get_all_ai_functions(self) -> List[AIFunction]:
        return self.get_function_set(None)
    
    @abstractmethod
    def get_function_set(self,set_name:str = None) -> List[AIFunction]:
        pass

    @abstractmethod
    def get_ai_action(self,op_name:str) -> AIAction:
        pass

    def get_all_ai_action(self) -> List[AIAction]:
        return self.get_action_set(None)

    @abstractmethod
    def get_action_set(self,set_name:str = None) -> List[AIFunction]:
        pass
    
    def __getitem__(self, key):
        return self.get_value(key)
    
    @abstractmethod
    def get_value(self,key:str) -> Optional[str]:
        pass

    #def list_actions(self,path:str) -> List[AIAction]:
    #    return "No more actions!"
    
    #def list_functions(self,path:str) -> List[AIFunction]:
    #    return "No more tool functions!"

class GlobaToolsLibrary:
    _instance = None
    @classmethod
    def get_instance(cls) -> 'GlobaToolsLibrary':
        if cls._instance is None:
            cls._instance = GlobaToolsLibrary()
        return cls._instance

    def __init__(self,global_env_name:str = None) -> None:
        self.all_preset_context  = {}
        self.all_tool_functions : Dict[str,AIFunction] = {}
        self.all_action_sets : Dict[str,Set[str]] = {}
        self.all_function_sets : Dict[str,Set[str]] = {}
    
    def register_prset_context(self,preset_id:str,context) -> None:
        self.all_preset_context[preset_id] = context

    def get_preset_context(self,preset_id:str):
        return self.all_preset_context.get(preset_id)
    
    def register_tool_function(self,function:AIFunction) -> None:
        if self.all_tool_functions.get(function.get_id()):
            logger.warning(f"Tool function {function.get_id()} already exists! will be replaced!")
            
        self.all_tool_functions[function.get_id()] = function

    def get_tool_function(self,function_name:str) -> AIFunction:
        return self.all_tool_functions.get(function_name)

    def register_function_set(self,set_name:str,function_set:Set[str]) -> None:
        self.all_function_sets[set_name] = function_set

    def get_function_set(self,set_name:str) -> Set[str]:
        return self.all_function_sets.get(set_name)  

class SimpleLLMContext(LLMProcessContext):
    def __init__(self) -> None:
        super().__init__()
        self.parent = None
        self.values : Dict[str,str] = {}
        self.values_callback = {}

        self.functions: Dict[str,AIFunction] = {}
        self.func_sets : Dict[str,Dict[str,AIFunction]] = {}
        self.actions: Dict[str,AIAction] = {}
        self.action_sets : Dict[str,Dict[str,AIAction]] = {}

    def load_action_set_from_config(self,preset,config:Dict[str,str]) -> Dict:
        if preset is None:
            result = {}
        else:
            result = preset

        enable_actions = config.get("enable")
        if enable_actions:
            for action_id in enable_actions:
                ai_func = GlobaToolsLibrary.get_instance().get_tool_function(action_id)
                if ai_func:
                    result[action_id] = LLMProcessContext.function2action(ai_func)
                else:
                    func_set = GlobaToolsLibrary.get_instance().get_function_set(action_id)
                    if func_set:
                        for _func_id in func_set:
                            ai_func = GlobaToolsLibrary.get_instance().get_tool_function(_func_id)
                            if ai_func:
                                result[_func_id] = LLMProcessContext.function2action(ai_func)
                    else:
                        logger.error(f"load_action_set_from_config failed! enable action id {action_id} not found!")
                        return None

        disable_actions = config.get("disable")
        if disable_actions:
            for disable_action in disable_actions:
                if result.get(disable_action):
                    result.pop(disable_action)
                else:
                    func_set = GlobaToolsLibrary.get_instance().get_function_set(action_id)
                    if func_set:
                        for _func_id in func_set:
                            if result.get(_func_id):
                                result.pop(_func_id)
                    else:
                        logger.error(f"load_action_set_from_config failed! disable action id {action_id} not found!")
                        return None
                
        return result
    
    def load_function_set_from_config(self,preset,config:Dict) -> Dict[str,AIFunction]:
        if preset is None:
            result = {}
        else:
            result = preset

        enable_functions = config.get("enable")
        if enable_functions:
            for func_id in enable_functions:
                ai_func = GlobaToolsLibrary.get_instance().get_tool_function(func_id)
                if ai_func:
                    result[func_id] = ai_func
                else:
                    func_set = GlobaToolsLibrary.get_instance().get_function_set(func_id)
                    if func_set:
                        for func_id in func_set:
                            ai_func = GlobaToolsLibrary.get_instance().get_tool_function(func_id)
                            if ai_func:
                                result[func_id] = ai_func
                            else:
                                logger.error(f"load_function_set_from_config failed! enable function id {func_id} not found!")
                                return None
                    else:
                        logger.error(f"load_function_set_from_config failed! enable function id {func_id} not found!")
                        return None


        disable_functions = config.get("disable")
        if disable_functions:
            for disable_function in disable_functions:
                if result.get(disable_function):
                    result.pop(disable_function)
                else:
                    func_set = GlobaToolsLibrary.get_instance().get_function_set(func_id)
                    if func_set:
                        for func_id in func_set:
                            if result.get(func_id):
                                result.pop(func_id)
                    else:
                        logger.error(f"load_function_set_from_config failed! disable function id {disable_function} not found!")
                        return None
                
        return result

    def load_from_config(self,config:Dict[str,str]) -> bool:
        preset = config.get("preset")
        if preset:
            self.parent:SimpleLLMContext = GlobaToolsLibrary.get_instance().get_preset_context(preset)
            if self.parent is None:
                logger.error(f"preset context {preset} not found!")
                return False
            
            self.values = self.parent.values
            self.values_callback = self.parent.values_callback
            self.actions = self.parent.actions
            self.functions = self.parent.functions
            self.action_sets = self.parent.action_sets
            self.func_sets = self.parent.func_sets

        action_def:Dict= config.get("actions")
        if action_def:
            self.actions = self.load_action_set_from_config(self.actions,action_def)
            if self.actions is None:
                logger.error(f"load_from_config failed! load_action_set_from_config failed!")
                return False
        
            for set_name in action_def.keys():
                if set_name == "enable":
                    continue
                if set_name == "disable":
                    continue

                sub_set = config.get(set_name)
                self.action_sets[set_name] = self.load_action_set_from_config(None,sub_set)
                if self.action_sets[set_name] is None:
                    logger.error(f"load_from_config failed! load_action_set_from_config failed!")
                    return False
        
        function_def:Dict = config.get("functions")
        if function_def:
            self.functions = self.load_function_set_from_config(self.functions,function_def)
            if self.functions is None:
                logger.error(f"load_from_config failed! load_function_set_from_config failed!")
                return False
            
            for set_name in function_def.keys():
                if set_name == "enable":
                    continue
                if set_name == "disable":
                    continue

                sub_set = config.get(set_name)
                self.func_sets[set_name] = self.load_function_set_from_config(None,sub_set)
                if self.func_sets[set_name] is None:
                    logger.error(f"load_from_config failed! load_function_set_from_config failed!")
                    return False

        #values_def = config.get("values")
        #if values_def:
        #    for key,value in values_def.items():
        #        self.values[key] = value

    def get_value(self,key:str) -> Optional[str]:
        callback = self.values_callback.get(key)
        if callback:
            return callback()
        return self.values.get(key)
    
    def set_value_callback(self,key:str,callback:Callable[[],str]) -> None:
        self.values_callback[key] = callback

    def set_value(self,key:str,value:str):
        self.values[key] = value

    def get_ai_function(self,func_name:str) -> AIFunction:
        for func in self.functions.values():
            if func.get_name() == func_name:
                return func
        #for set_name in self.func_sets.keys():
        #    func = self.func_sets[set_name].get(func_name)
        #    if func is not None:
        #        return func
        return None

    def get_function_set(self,set_name:str = None) -> List[AIFunction]:
        if self.functions is None:
            return None
        
        if set_name is None:
            return self.functions.values()
        else:
            func_set =  self.func_sets.get(set_name)
            if func_set:
                return func_set.values()
        return None

    
    def get_ai_action(self,op_name:str) -> AIAction:
        for action in self.actions.values():
            if action.get_name() == op_name:
                return action

        return None
    
    def get_action_set(self,set_name:str = None) -> List[AIFunction]:
        if self.actions is None:
            return None
        
        if set_name is None:
            return self.actions.values()
        else:
            action_set =  self.action_sets.get(set_name)
            if action_set:
                return action_set.values()
        return None


