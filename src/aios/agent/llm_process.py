# Old name is behavior, I belive new name "llm_process" is better
from abc import ABC,abstractmethod
import copy
import json
import shlex
from typing import Any, Callable, Coroutine, Optional,Dict,Awaitable,List
from enum import Enum

from aios.agent.chatsession import AIChatSession

from ..utils import video_utils

from ..proto.compute_task import *
from ..proto.ai_function import *

from .agent_base import *
from .agent_memory import *

from ..frame.compute_kernel import *
from ..environment.environment import *
from ..environment.workspace_env import *

import logging
logger = logging.getLogger(__name__)

MIN_PREDICT_TOKEN_LEN = 32

class LLMProcessContext:
    def __init__(self) -> None:
        pass

class BaseLLMProcess(ABC):
    def __init__(self) -> None:
        self.behavior:str = None #行为名字
        self.goal:str = None #目标
        self.input_example:str= None #输入样例
        self.result_example:str = None #llm_result样例
        
        self.enable_json_resp = False
        self.model_name = "gpt-4"
        self.max_token = 1000 # result_token
        self.max_prompt_token = 1000 # not include input prompt
        self.timeout = 1800 # 30 min

        self.envs : Dict[str,BaseEnvironment] = []
        self.env : CompositeEnvironment = None

    @abstractmethod
    async def prepare_prompt(self,input:Dict) -> LLMPrompt:
        pass

    @abstractmethod
    async def get_inner_function(self,func_name:str) -> AIFunction:
        pass

    @abstractmethod
    async def exec_actions(self,actions:List[ActionItem],input:Dict,llm_result:LLMResult) -> bool:
        pass

    @abstractmethod
    async def load_from_config(self,config:dict) -> bool:
        #self.behavior = config.get("behavior")
        #self.goal = config.get("goal")
        self.input_example = config.get("input_example")
        self.result_example = config.get("result_example")

        if config.get("model_name"):
            self.model_name = config.get("model_name")
        if config.get("enable_json_resp"):
            self.enable_json_resp = config.get("enable_json_resp") == "true"
        if config.get("max_token"):
            self.max_token = config.get("max_token")
        if config.get("timeout"):
            self.timeout = config.get("timeout")
        

        return True
    
    @abstractmethod
    async def initial(self,params:Dict = None) -> bool:
        pass

    def append_envs(self,envs:Dict[str,BaseEnvironment]):
        self.envs.update(envs)
        self.env = CompositeEnvironment(self.envs)
    
    def _format_content_by_env_value(self,content:str,env)->str:
        return content.format_map(env)

    async def _execute_inner_func(self,inner_func_call_node,prompt: LLMPrompt,stack_limit = 5) -> ComputeTaskResult:
        arguments = None
        try:
            func_name = inner_func_call_node.get("name")
            arguments = json.loads(inner_func_call_node.get("arguments"))
            logger.info(f"LLMProcess execute inner func:{func_name} :\n\t {json.dumps(arguments)}")

            func_node : AIFunction = await self.get_inner_function(func_name)
            if func_node is None:
                result_str:str = f"execute {func_name} error,function not found"
            else:
                result_str:str = await func_node.execute(**arguments)
        except Exception as e:
            result_str = f"execute {func_name} error:{str(e)}"
            logger.error(f"LLMProcess execute inner func:{func_name} error:\n\t{e}")

        logger.info("LLMProcess execute inner func result:" + result_str)

        prompt.messages.append({"role":"function","content":result_str,"name":func_name})
        if self.enable_json_resp:
            resp_mode = "json"
        else:
            resp_mode = "text"

        max_result_token = self.max_token - ComputeKernel.llm_num_tokens(prompt,self.model_name)
        if max_result_token < MIN_PREDICT_TOKEN_LEN:
            task_result = ComputeTaskResult()
            task_result.result_code = ComputeTaskResultCode.ERROR
            task_result.error_str = f"prompt too long,can not predict"
            return task_result
       
        task_result: ComputeTaskResult = await (ComputeKernel.get_instance().do_llm_completion(
            prompt,
            resp_mode=resp_mode,
            mode_name=self.model_name,
            max_token=max_result_token,
            inner_functions=prompt.inner_functions, #NOTICE: inner_function in prompt can be a subset of get_inner_function
            timeout=self.timeout))

        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"llm compute error:{task_result.error_str}")
            return task_result

        inner_func_call_node = None
        if stack_limit > 0:
            result_message : dict = task_result.result.get("message")
            if result_message:
                inner_func_call_node = result_message.get("function_call")
                if inner_func_call_node:
                    func_msg = copy.deepcopy(result_message)
                    del func_msg["tool_calls"]#TODO: support tool_calls?
                    prompt.messages.append(func_msg)
        else:
            logger.error(f"inner function call stack limit reached")
            task_result.result_code = ComputeTaskResultCode.ERROR
            task_result.error_str = "inner function call stack limit reached"
            return task_result

        if inner_func_call_node:
            return await self._execute_inner_func(inner_func_call_node,prompt,stack_limit-1)
        else:
            return task_result

    async def process(self,input:Dict) -> LLMResult:
        if self.enable_json_resp:
            resp_mode = "json"
        else:
            resp_mode = "text"

        prompt = await self.prepare_prompt(input)
        max_result_token = self.max_token - ComputeKernel.llm_num_tokens(prompt,self.model_name)
        if max_result_token < MIN_PREDICT_TOKEN_LEN:
            return LLMResult.from_error_str(f"prompt too long,can not predict")
        
        task_result: ComputeTaskResult = await (ComputeKernel.get_instance().do_llm_completion(
                prompt,
                resp_mode=resp_mode,
                mode_name=self.model_name,
                max_token=max_result_token,
                inner_functions=prompt.inner_functions, #NOTICE: inner_function in prompt can be a subset of get_inner_function
                timeout=self.timeout))
        
        if task_result.result_code != ComputeTaskResultCode.OK:
            err_str = f"do_llm_completion error:{task_result.error_str}"
            logger.error(err_str)
            return LLMResult.from_error_str(err_str)
        
        result_message = task_result.result.get("message")
        inner_func_call_node = None
        if result_message:
            inner_func_call_node = result_message.get("function_call")

        if inner_func_call_node:
            call_prompt : LLMPrompt = copy.deepcopy(prompt)
            func_msg = copy.deepcopy(result_message)
            del func_msg["tool_calls"]
            call_prompt.messages.append(func_msg)
            task_result = await self._execute_inner_func(inner_func_call_node,call_prompt)

        # parse task_result to LLM Result
        if self.enable_json_resp:
            llm_result = LLMResult.from_json_str(task_result.result_str)
        else:
            llm_result = LLMResult.from_str(task_result.result_str)

        # use action to save history?
        if llm_result.action_list or len(llm_result.action_list) > 0:
            await self.exec_actions(llm_result.action_list,input,llm_result)

        return llm_result
    
class LLMAgentMessageProcess(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

        self.role_description:str = None
        self.process_description:str = None
        self.reply_format:str = None
        self.context : str = None

        self.known_info_tips :str = None
        self.tools_tips:str = None

        self.enable_inner_functions : Dict[str,bool] = None
        self.enable_actions : Dict[str,AIOperation] = None
        self.actions_desc : Dict[str,Dict] = None
        self.workspace : WorkspaceEnvironment = None

        self.memory : AgentMemory = None
        self.enable_kb = False
        self.kb = None

    def init_actions(self):
        self.enable_actions = {}
        self.actions_desc = {}
        self.enable_actions.update(self.memory.get_actions())
        if self.workspace:
            self.enable_actions.update(self.workspace.get_actions())
        if self.enable_kb:
            self.enable_actions.update(self.kb.get_actions())

        for name,op in self.enable_actions.items():
            self.actions_desc[name] = op.get_description()
        
    async def initial(self,params:Dict = None) -> bool:
        self.memory = params.get("memory")
        if self.memory is None:
            logger.error(f"LLMAgeMessageProcess initial failed! memory not found")
            return False
        
        self.init_actions()
        return True

    async def load_default_config(self) -> bool:
        return True
        
        
    async def load_from_config(self, config: dict,is_load_default=True) -> Coroutine[Any, Any, bool]:
        if is_load_default:
            await self.load_default_config()

        if await super().load_from_config(config) is False:
            return False
        
        self.role_description = config.get("role_desc")
        if self.role_description is None:
            logger.error(f"role_description not found in config")
            return False
        
        if config.get("process_description"):
            self.process_description = config.get("process_description")
        
        if config.get("reply_format"):
            self.reply_format = config.get("reply_format")

        if config.get("context"):
            self.context = config.get("context")

        if config.get("known_info_tips"):
            self.known_info_tips = config.get("known_info_tips")

        if config.get("tools_tips"):
            self.tools_tips = config.get("tools_tips")  

        if config.get("enable_kb"):
            self.enable_kb = config.get("enable_kb") == "true"
        
        if config.get("enable_function"):
            self.enable_inner_functions = config.get("enable_function")
        
        if config.get("enable_actions"):
            self.enable_actions = config.get("enable_actions")

        

    async def get_prompt_from_msg(self,msg:AgentMsg) -> LLMPrompt:
        msg_prompt = LLMPrompt()
        if msg.is_image_msg():
            image_prompt, images = msg.get_image_body()
            if image_prompt is None:
                msg_prompt.messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": self.check_and_to_base64(image)}} for image in images]}]
            else:
                content = [{"type": "text", "text": image_prompt}]
                content.extend([{"type": "image_url", "image_url": {"url": self.check_and_to_base64(image)}} for image in images])
                msg_prompt.messages = [{"role": "user", "content": content}]
        elif msg.is_video_msg():
            video_prompt, video = msg.get_video_body()
            frames = video_utils.extract_frames(video, (1024, 1024))
            if video_prompt is None:
                msg_prompt.messages = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": frame}} for frame in frames]}]
            else:
                content = [{"type": "text", "text": video_prompt}]
                content.extend([{"type": "image_url", "image_url": {"url": frame}} for frame in frames])
                msg_prompt.messages = [{"role": "user", "content": content}]
        elif msg.is_audio_msg():
            audio_file = msg.body
            resp = await (ComputeKernel.get_instance().do_speech_to_text(audio_file, None, prompt=None, response_format="text"))
            if resp.result_code != ComputeTaskResultCode.OK:
                error_resp = msg.create_error_resp(resp.error_str)
                return error_resp
            else:
                msg.body = resp.result_str
                msg_prompt.messages = [{"role":"user","content":resp.result_str}]
        else:
            msg_prompt.messages = [{"role":"user","content":msg.body}]

        return msg_prompt
    
    async def get_action_desc(self) -> Dict:
        result = {}
        for name,op in self.enable_actions.items():
            result[name] = op.get_description()
        return result

    async def sender_info(self,msg:AgentMsg)->str:
        sender_id = msg.sender
        #TODO Is sender an agent?
        return await self.memory.get_contact_summary(sender_id)

    async def load_chatlogs(self,msg:AgentMsg)->str:
        ## like
        #sender,[2023-11-1 12:00:00]
        #content
        return await self.memory.load_chatlogs(msg)

    async def get_log_summary(self,msg:AgentMsg)->str:
        return await self.memory.get_log_summary(msg)
        

    async def get_extend_known_info(self,msg:AgentMsg,prompt:LLMPrompt)->str:
        return None

    async def prepare_prompt(self,input:Dict) -> LLMPrompt:
        prompt = LLMPrompt()
        # User Prompt 
        ## Input Msg
        msg : AgentMsg = input.get("msg")
        if msg is None:
            logger.error(f"LLMAgeMessageProcess prepare_prompt failed! input msg not found")
            return None
        msg_prompt = await self.get_prompt_from_msg(msg)
        if msg_prompt is None:
            logger.error(f"LLMAgeMessageProcess prepare_prompt failed! get_prompt_from_msg return None")
            return None
        prompt.append(msg_prompt)

        system_prompt_dict = {}

        # System Prompt
        ## LLM的身份说明
        system_prompt_dict["role_description"] = self.role_description
        #prompt.append_system_message(self.role_description)

        ## 处理信息的流程说明
        system_prompt_dict["process_rule"] = self.process_description
        #prompt.append_system_message(self.process_description)
        ### 回复的格式
        system_prompt_dict["reply_format"] = self.reply_format
        #prompt.append_system_message(self.reply_format)
        ### 修改chatlog的action
        ### 修改todo/task的action
        ### workspace提供的额外的action
        system_prompt_dict["support_actions"] = await self.get_action_desc()
        #prompt.append_system_message(await self.get_action_desc())

        ## Context （文本替换）,是否应该覆盖全部消息
        context = self._format_content_by_env_value(self.context,msg.context_info)
        system_prompt_dict["context"] = context
        #prompt.append_system_message(context)
               
        ## 已知信息  
        known_info = {}
        #prompt.append_system_message(self.known_info_tips)
        ### 信息发送者资料
        known_info["sender_info"] = await self.sender_info(msg)
        #prompt.append_system_message(await self.sender_info(self,msg))
        ### 近期的聊天记录
        chat_record = await self.load_chatlogs(msg)
        if chat_record:
            if len(chat_record) > 4:
                known_info["chat_record"] = chat_record
        #prompt.append_system_message(await self.load_chatlogs(self,msg))
        ### 交流总结
        summary = await self.get_log_summary(msg)
        if summary:
            if len(summary) > 4:
                known_info["summary"] = summary
        #prompt.append_system_message(await self.get_log_summary(self,msg))
        system_prompt_dict["known_info"] = known_info
        
        ## 可以使用的tools(inner function)的解释，注意不定义该tips,则不会导入任何workspace中的tools
        if self.tools_tips:
            system_prompt_dict["tools_tips"] = self.tools_tips
            #prompt.append_system_message(self.tools_tips)
            prompt.inner_functions.extend(self.get_inner_function_desc_from_env())

        ## 给予查询KB的权限    
        if self.enable_kb:        
            prompt.inner_functions.extend(self.get_inner_function_desc_from_kb())

        prompt.append_system_message(json.dumps(system_prompt_dict))
        ## 扩展已知信息 (这可能是一个LLM过程)
        prompt.append_system_message(await self.get_extend_known_info(msg,prompt))

        return prompt
    

    async def get_inner_function(self,func_name:str) -> AIFunction:
        return None

    async def exec_actions(self,actions:List[ActionItem],input:Dict,llm_result:LLMResult) -> bool:
        msg = input.get("msg")
        if msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
            resp_msg = msg.create_group_resp_msg(self.memory.agent_id,llm_result.resp)
        else:
            resp_msg = msg.create_resp_msg(llm_result.resp)
        
        llm_result.raw_result["resp_msg"] = resp_msg

        for action_item in actions:
            op : AIOperation = self.enable_actions.get(action_item.name)
            if op:
                if action_item.parms is None:
                    action_item.parms = {}

                action_item.parms["input"] = input
                action_item.parms["resp_msg"] = resp_msg  
                action_item.parms["llm_result"] = llm_result
                action_item.parms["start_at"] = datetime.now()
                action_item.parms["result"] = await op.execute(action_item.parms)
                action_item.parms["end_at"] = datetime.now()
            else:
                logger.warn(f"action {action_item.name} not found")
                return False
            
        return True

        

class ReviewTaskProcess(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self) -> LLMPrompt:
        prompt = LLMPrompt()
        pass  

    async def get_inner_function(self,func_name:str) -> AIFunction:
        pass

    async def exec_actions(self,actions:List[ActionItem]) -> bool:
        pass

class DoTodoProcess(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self) -> LLMPrompt:
        prompt = LLMPrompt()
        pass  

    async def get_inner_function(self,func_name:str) -> AIFunction:
        pass

    async def exec_actions(self,actions:List[ActionItem]) -> bool:
        pass


class CheckTodoProcess(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self) -> LLMPrompt:
        prompt = LLMPrompt()
        pass  

    async def get_inner_function(self,func_name:str) -> AIFunction:
        pass

    async def exec_actions(self,actions:List[ActionItem]) -> bool:
        pass

class SelfLearningProcess(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self) -> LLMPrompt:
        prompt = LLMPrompt()
        pass  

    async def get_inner_function(self,func_name:str) -> AIFunction:
        pass

    async def exec_actions(self,actions:List[ActionItem]) -> bool:
        pass

class SelfThinkingProcess(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self) -> LLMPrompt:
        prompt = LLMPrompt()
        pass  

    async def get_inner_function(self,func_name:str) -> AIFunction:
        pass

    async def exec_actions(self,actions:List[ActionItem]) -> bool:
        pass
    
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





