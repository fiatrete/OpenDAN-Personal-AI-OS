# Old name is behavior, I belive new name "llm_process" is better
# pylint:disable=E0402
from ..utils import video_utils,image_utils

from ..proto.compute_task import LLMPrompt,LLMResult,ComputeTaskResult,ComputeTaskResultCode
from ..proto.ai_function import AIFunction,AIAction,ActionNode
from ..proto.agent_msg import AgentMsg,AgentMsgType

from .agent_memory import AgentMemory
from .workspace import AgentWorkspace
from .llm_context import LLMProcessContext,GlobaToolsLibrary, SimpleLLMContext

from ..frame.compute_kernel import ComputeKernel

from abc import ABC,abstractmethod
import copy
import json
import datetime
from datetime import datetime
from typing import Any, Callable, Coroutine, Optional,Dict,Awaitable,List
from enum import Enum
import logging

logger = logging.getLogger(__name__)

MIN_PREDICT_TOKEN_LEN = 32

class BaseLLMProcess(ABC):
    def __init__(self) -> None:
        self.behavior:str = None #行为名字
        self.goal:str = None #目标
        self.input_example:str= None #输入样例
        self.result_example:str = None #llm_result样例
        
        self.enable_json_resp = False
        #None means system default,
        # TODO: support abcstract model name like: local-hight,local-low,local-medium,remote-hight,remote-low,remote-medium
        self.model_name = None 
        self.max_token = 1000 # result_token
        self.max_prompt_token = 1000 # not include input prompt
        self.timeout = 1800 # 30 min

        self.llm_context:LLMProcessContext = None

    @abstractmethod
    async def prepare_prompt(self,input:Dict) -> LLMPrompt:
        pass

    @abstractmethod
    async def get_inner_function_for_exec(self,func_name:str) -> AIFunction:
       pass

    @abstractmethod
    def prepare_inner_function_context_for_exec(self,inner_func_name:str,parameters:Dict):
        return 
    
    @abstractmethod
    async def post_llm_process(self,actions:List[ActionNode],input:Dict,llm_result:LLMResult) -> bool:
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
    
    def _format_content_by_env_value(self,content:str,env)->str:
        return content.format_map(env)


    async def _execute_inner_func(self,inner_func_call_node:Dict,prompt: LLMPrompt,stack_limit = 1) -> ComputeTaskResult:
        arguments = None
        stack_limit = stack_limit - 1
        try:
            func_name = inner_func_call_node.get("name")
            arguments = json.loads(inner_func_call_node.get("arguments"))
            logger.info(f"LLMProcess execute inner func:{func_name} :\n\t {json.dumps(arguments,ensure_ascii=False)}")

            func_node : AIFunction = await self.get_inner_function_for_exec(func_name)
            if func_node is None:
                result_str:str = f"execute {func_name} error,function not found"
            else:
                self.prepare_inner_function_context_for_exec(func_name,arguments)
                result_str:str = await func_node.execute(arguments)
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
        
        if stack_limit > 0:
            inner_functions=prompt.inner_functions
        else:
            inner_functions = None
       
        task_result: ComputeTaskResult = await (ComputeKernel.get_instance().do_llm_completion(
            prompt,
            resp_mode=resp_mode,
            mode_name=self.model_name,
            max_token=max_result_token,
            inner_functions=inner_functions, #NOTICE: inner_function in prompt can be a subset of get_inner_function
            timeout=self.timeout))

        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"llm compute error:{task_result.error_str}")
            return task_result

        inner_func_call_node = None
 
        result_message : dict = task_result.result.get("message")
        if result_message:
            inner_func_call_node = result_message.get("function_call")
            if inner_func_call_node:
                func_msg = copy.deepcopy(result_message)
                del func_msg["tool_calls"]#TODO: support tool_calls?
                prompt.messages.append(func_msg)


        if inner_func_call_node:
            return await self._execute_inner_func(inner_func_call_node,prompt,stack_limit-1)
        else:
            return task_result

    async def process(self,input:Dict) -> LLMResult:
        if self.enable_json_resp:
            resp_mode = "json"
        else:
            resp_mode = "text"

        # Action define in prompt, will be execute after llm compute
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
        await self.post_llm_process(llm_result.action_list,input,llm_result)

        return llm_result
    
class LLMAgentBaseProcess(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

        self.role_description:str = None
        self.process_description:str = None
        self.reply_format:str = None
        self.context : str = None
        
        self.workspace : AgentWorkspace = None # If Workspace is not none , enable Agent Tasklist
        self.memory : AgentMemory = None
        self.enable_kb : bool = False
        self.kb = None    

    async def initial(self,params:Dict = None) -> bool:
        self.memory = params.get("memory")
        if self.memory is None:
            logger.error(f"LLMAgeMessageProcess initial failed! memory not found")
            return False
        self.workspace = params.get("workspace")

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

        self.llm_context = SimpleLLMContext()
        if config.get("llm_context"):
            self.llm_context.load_from_config(config.get("llm_context"))

        if config.get("enable_kb"):
            self.enable_kb = config.get("enable_kb") == "true"

    def prepare_role_system_prompt(self,context_info:Dict) -> Dict:
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

        ## Context
        context = self._format_content_by_env_value(self.context,context_info)
        system_prompt_dict["context"] = context
        #prompt.append_system_message(context)

        system_prompt_dict["support_actions"] = self.get_action_desc()

        return system_prompt_dict

    def prepare_inner_function_context_for_exec(self,inner_func_name:str,parameters:Dict):
        parameters["_workspace"] = self.workspace  

    def get_action_desc(self) -> Dict:
        result = {}
        actions_list = self.llm_context.get_all_ai_action()
        for action in actions_list:
            result[action.get_name()] = action.get_description()
        return result
    
    async def get_inner_function_for_exec(self,func_name:str) -> AIFunction:
        return self.llm_context.get_ai_function(func_name)
    
    async def _execute_actions(self,actions:List[ActionNode],action_params:Dict):
        for action_item in actions:
            op : AIAction = self.llm_context.get_ai_action(action_item.name)
            if op:
                if action_item.parms is None:
                    action_item.parms = {}
                
                real_parms = {**action_params,**action_item.parms}

                action_item.parms["_result"] = await op.execute(real_parms)
                action_item.parms["_end_at"] = datetime.now()
            else:
                logger.warn(f"action {action_item.name} not found")
                return False

    
class AgentMessageProcess(LLMAgentBaseProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_default_config(self) -> bool:
        return True
        
    async def load_from_config(self, config: dict,is_load_default=True) -> Coroutine[Any, Any, bool]:
        if is_load_default:
            await self.load_default_config()

        if await super().load_from_config(config) is False:
            return False
         

    def check_and_to_base64(self, image_path: str) -> str:
        if image_utils.is_file(image_path):
            return image_utils.to_base64(image_path, (1024, 1024))
        else:
            return image_path
             
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
        context_info = input.get("context_info")
        if msg is None:
            logger.error(f"LLMAgeMessageProcess prepare_prompt failed! input msg not found")
            return None
        msg_prompt = await self.get_prompt_from_msg(msg)
        if msg_prompt is None:
            logger.error(f"LLMAgeMessageProcess prepare_prompt failed! get_prompt_from_msg return None")
            return None
        prompt.append(msg_prompt)

        ## 通用的角色相关的系统提示词
        system_prompt_dict = self.prepare_role_system_prompt(context_info)
               
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
        
        prompt.inner_functions =LLMProcessContext.aifunctions_to_inner_functions(self.llm_context.get_all_ai_functions())
        if self.workspace:
            #TODO eanble workspace functions?
            logger.info(f"workspace is not none,enable workspace functions")

        ## 给予查询KB的权限    
        if self.enable_kb:        
            logger.info(f"enable kb")
           

        prompt.append_system_message(json.dumps(system_prompt_dict,ensure_ascii=False))
        ## 扩展已知信息 (这可能是一个LLM过程)
        prompt.append_system_message(await self.get_extend_known_info(msg,prompt))

        return prompt
    

    async def post_llm_process(self,actions:List[ActionNode],input:Dict,llm_result:LLMResult) -> bool:
        msg:AgentMsg = input.get("msg")
        if msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
            resp_msg = msg.create_group_resp_msg(self.memory.agent_id,llm_result.resp)
        else:
            resp_msg = msg.create_resp_msg(llm_result.resp)
        
        llm_result.raw_result["_resp_msg"] = resp_msg

        action_params = {}
        action_params["_input"] = input
        action_params["_memory"] = self.memory
        action_params["_workspace"] = self.workspace
        action_params["_resp_msg"] = resp_msg  
        action_params["_llm_result"] = llm_result
        action_params["_agentid"] = self.memory.agent_id
        action_params["_start_at"] = datetime.now()

        await self._execute_actions(actions,action_params)

        chatsession = self.memory.get_session_from_msg(msg)
        chatsession.append(msg)
        chatsession.append(resp_msg)  

        return True

class AgentSelfLearning(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False

    async def prepare_prompt(self) -> LLMPrompt:
        prompt = LLMPrompt()
        pass  

    async def get_inner_function_for_exec(self,func_name:str) -> AIFunction:
        pass

    async def post_llm_process(self,actions:List[ActionNode]) -> bool:
        pass

class AgentSelfThinking(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()

    async def load_from_config(self, config: dict) -> Coroutine[Any, Any, bool]:
        if await super().load_from_config(config) is False:
            return False


    async def _get_history_prompt_for_think(self,chatsession,summary:str,system_token_len:int,pos:int)->(LLMPrompt,int):
        history_len = (self.max_token_size * 0.7) - system_token_len

        messages = chatsession.read_history(self.history_len,pos,"natural") # read
        result_token_len = 0
        result_prompt = LLMPrompt()
        have_summary = False
        if summary is not None:
            if len(summary) > 1:
                have_summary = True

        if have_summary:
                result_prompt.messages.append({"role":"user","content":summary})
                result_token_len -= len(summary)
        else:
            result_prompt.messages.append({"role":"user","content":"There is no summary yet."})
            result_token_len -= 6

        read_history_msg = 0
        history_str : str = ""
        for msg in messages:
            read_history_msg += 1
            dt = datetime.datetime.fromtimestamp(float(msg.create_time))
            formatted_time = dt.strftime('%y-%m-%d %H:%M:%S')
            record_str = f"{msg.sender},[{formatted_time}]\n{msg.body}\n"
            history_str = history_str + record_str

            history_len -= len(msg.body)
            result_token_len += len(msg.body)
            if history_len < 0:
                logger.warning(f"_get_prompt_from_session reach limit of token,just read {read_history_msg} history message.")
                break

        result_prompt.messages.append({"role":"user","content":history_str})
        return result_prompt,pos+read_history_msg

    async def _think_chatsession(self,session_id):
        if self.agent_think_prompt is None:
            return
        logger.info(f"agent {self.agent_id} think session {session_id}")
        chatsession = AIChatSession.get_session_by_id(session_id,self.chat_db)

        while True:
            cur_pos = chatsession.summarize_pos
            summary = chatsession.summary
            prompt:LLMPrompt = LLMPrompt()
            #prompt.append(self._get_agent_prompt())
            prompt.append(await self._get_agent_think_prompt())
            system_prompt_len = ComputeKernel.llm_num_tokens(prompt)
            #think env?
            history_prompt,next_pos = await self._get_history_prompt_for_think(chatsession,summary,system_prompt_len,cur_pos)
            prompt.append(history_prompt)
            is_finish = next_pos - cur_pos < 2
            if is_finish:
                logger.info(f"agent {self.agent_id} think session {session_id} is finished!,no more history")
                break
            #3) llm summarize chat history
            task_result:ComputeTaskResult = await self.do_llm_complection(prompt)
            if task_result.result_code != ComputeTaskResultCode.OK:
                logger.error(f"think_chatsession llm compute error:{task_result.error_str}")
                break
            else:
                new_summary= task_result.result_str
                logger.info(f"agent {self.agent_id} think session {session_id} from {cur_pos} to {next_pos} summary:{new_summary}")
                chatsession.update_think_progress(next_pos,new_summary)
        return

    async def prepare_prompt(self) -> LLMPrompt:
        prompt = LLMPrompt()
        pass  

    async def get_inner_function_for_exec(self,func_name:str) -> AIFunction:
        pass

    async def post_llm_process(self,actions:List[ActionNode]) -> bool:
        pass

class AgentSelfImprove(BaseLLMProcess):
    def __init__(self) -> None:
        super().__init__()    



