# pylint:disable=E0402
import copy
from enum import Enum
import json
import shlex
import uuid
import time
from typing import List, Union,Dict
from .ai_function import AIFunction,ActionNode
from .agent_msg import AgentMsg
from ..knowledge import ObjectID
from ..storage.storage import AIStorage


import logging

logger = logging.getLogger(__name__)

class ComputeTaskResultCode(Enum):
    OK = 0
    TIMEOUT = 1
    NO_WORKER = 2
    ERROR = 3


class ComputeTaskState(Enum):
    DONE = 0
    INIT = 1
    RUNNING = 2
    ERROR = 3
    PENDING = 4

class ComputeTaskType(Enum):
    NONE = "None"
    LLM_COMPLETION = "llm_completion"
    TEXT_EMBEDDING ="text_embedding"
    IMAGE_EMBEDDING ="image_embedding"

    TEXT_2_IMAGE = "text_2_image"
    IMAGE_2_TEXT = "image_2_text"
    IMAGE_2_IMAGE = "image_2_image"
    VOICE_2_TEXT = "voice_2_text"
    TEXT_2_VOICE = "text_2_voice"


# class Function(TypedDict, total=False):
#     name: Required[str]
#     """The name of the function to be called.

#     Must be a-z, A-Z, 0-9, or contain underscores and dashes, with a maximum length
#     of 64.
#     """

#     parameters: Required[shared_params.FunctionParameters]
#     """The parameters the functions accepts, described as a JSON Schema object.

#     See the [guide](https://platform.openai.com/docs/guides/gpt/function-calling)
#     for examples, and the
#     [JSON Schema reference](https://json-schema.org/understanding-json-schema/) for
#     documentation about the format.

#     To describe a function that accepts no parameters, provide the value
#     `{"type": "object", "properties": {}}`.
#     """

#     description: str
#     """
#     A description of what the function does, used by the model to choose when and
#     how to call the function.
#     """

class LLMPrompt:
    def __init__(self,prompt_str = None) -> None:
        self.messages : List[Dict] = []
        if prompt_str:
            self.messages.append({"role":"user","content":prompt_str})
        self.system_message : Dict = None
        self.inner_functions : List[Dict] = []

    def append_system_message(self,content:str):
        if content is None:
            return
        
        if self.system_message is None:
            self.system_message = {"role":"system","content":content}
        else:
            self.system_message["content"] += content
    
    def append_user_message(self,content:str):
        if content is None:
            return
        
        self.messages.append({"role":"user","content":content})

    def as_str(self)->str:
        result_str = ""
        if self.system_message:
            result_str = json.dumps(self.system_message,ensure_ascii=False)
        if self.messages:
            result_str += json.dumps(self.messages,ensure_ascii=False)
        if self.inner_functions:
            result_str += json.dumps(self.inner_functions,ensure_ascii=False)

        return result_str

    def to_message_list(self):
        result = []
        if self.system_message:
            result.append(self.system_message)
        result.extend(self.messages)
        return result
    
    

    def append(self,prompt:'LLMPrompt'):
        if prompt is None:
            return
        
        if prompt.inner_functions:
            if self.inner_functions is None:
                self.inner_functions = copy.deepcopy(prompt.inner_functions)
            else:
                self.inner_functions.extend(prompt.inner_functions)

        if prompt.system_message is not None:
            if self.system_message is None:
                self.system_message = copy.deepcopy(prompt.system_message)
            else:
                self.system_message["content"] += prompt.system_message.get("content")

        self.messages.extend(prompt.messages)

    def load_from_config(self,config:List[Dict]) -> bool:
        if isinstance(config,list) is not True:
            logger.error("prompt is not list!")
            return False
        self.messages : List[Dict] = []
        for msg in config:
            if msg.get("content"):
                if msg.get("role") == "system":
                    self.system_message = msg
                else:
                    self.messages.append(msg)
            else:
                logger.error("prompt message has no content!")
        return True


class LLMResultStates(Enum):
    IGNORE = "ignore"
    OK = "ok" # process done
    ERROR = "error"

class LLMResult:
    def __init__(self) -> None:
        self.state : str = LLMResultStates.IGNORE
        self.compute_error_str = None
        self.resp : str = "" # llm say:
        self.raw_result = None # raw result from compute kernel
        #self.inner_functions : List[AIFunction] = []
        self.action_list : List[ActionNode] = [] # op_list is a optimize design for saving token


    @classmethod
    def from_error_str(self,error_str:str) -> 'LLMResult':
        r = LLMResult()
        r.state = "error"
        r.compute_error_str = error_str
        return r

    @classmethod
    def from_json_str(self,llm_json_str:str) -> 'LLMResult':
        r = LLMResult()
        if llm_json_str is None:
            r.state = LLMResultStates.IGNORE
            return r
        if llm_json_str == "**IGNORE**":
            r.state = LLMResultStates.IGNORE
            return r
        
        r.state = LLMResultStates.OK

        llm_json = json.loads(llm_json_str)
        r.resp = llm_json.get("resp")
        r.raw_result = llm_json
        action_list = llm_json.get("actions")
        if action_list:
            for action in action_list:
                action_item = ActionNode.from_json(action)
                if action_item:
                    r.action_list.append(action_item)

        return r

    @classmethod
    def parse_action(cls,func_string:str):
        str_list = shlex.split(func_string)
        func_name = str_list[0]
        params = str_list[1:]
        return func_name, params
    
    @classmethod
    def from_str(self,llm_result_str:str,valid_func:List[str]=None) -> 'LLMResult':
        r = LLMResult()

        if llm_result_str is None:
            r.state = LLMResultStates.IGNORE
            return r
        if llm_result_str == "**IGNORE**":
            r.state = LLMResultStates.IGNORE
            return r

        if llm_result_str[0] == "{":
            return LLMResult.from_json_str(llm_result_str)

        lines = llm_result_str.splitlines()
        is_need_wait = False

        def check_args(action_item:ActionNode):
            match action_item.name:
                case "post_msg":# /post_msg $target_id
                    if len(action_item.args) != 1:
                        return False

                    new_msg = AgentMsg()
                    target_id = action_item.args[0]
                    msg_content = action_item.body
                    new_msg.set("",target_id,msg_content)
                    
                    return True

                    
            return False


        current_action : ActionNode = None
        for line in lines:
            if line.startswith("##/"):
                if current_action:
                    if check_args(current_action) is False:
                        r.resp += current_action.dumps()
                    else:
                        r.action_list.append(current_action)

                action_name,action_args = LLMResult.parse_action(line[3:])
                current_action = ActionNode(action_name,action_args)
            else:
                if current_action:
                    current_action.append_body(line + "\n")
                else:
                    r.resp += line + "\n"

        if current_action:
            if check_args(current_action) is False:
                r.resp += current_action.dumps()
            else:
                r.action_list.append(current_action)
        return r

class ComputeTask:
    def __init__(self) -> None:
        self.task_type = ComputeTaskType.NONE
        self.create_time = None

        self.task_id: str = None
        self.callchain_id: str = None
        self.params: dict = {}
        self.refers: dict = None
        self.pading_data: bytearray = None

        self.state = ComputeTaskState.INIT
        self.result = None
        self.error_str = None

    def set_llm_params(self, prompts, resp_mode,model_name, max_token_size, inner_functions = None, callchain_id=None):
        self.task_type = ComputeTaskType.LLM_COMPLETION
        self.create_time = time.time()
        self.task_id = uuid.uuid4().hex
        self.callchain_id = callchain_id
        self.params["prompts"] = prompts.to_message_list()
        self.params["resp_mode"] = resp_mode
        if model_name is None:
             model_name = AIStorage.get_instance().get_user_config().get_value("llm_model_name")
        self.params["model_name"] = model_name
        if max_token_size is None:
            self.params["max_token_size"] = 4000
        else:
            self.params["max_token_size"] = max_token_size

        if inner_functions is not None:
            self.params["inner_functions"] = inner_functions

    def set_text_embedding_params(self, input: str, model_name=None, callchain_id = None):
        self.task_type = ComputeTaskType.TEXT_EMBEDDING
        self.create_time = time.time()
        self.task_id = uuid.uuid4().hex
        self.callchain_id = callchain_id
        if model_name is not None:
            self.params["model_name"] = model_name
        else:
            self.params["model_name"] = "text-embedding-ada-002"
        self.params["input"] = input

    def set_image_embedding_params(self, input = Union[ObjectID, bytes], model_name=None, callchain_id = None):
        self.task_type = ComputeTaskType.IMAGE_EMBEDDING
        self.create_time = time.time()
        self.task_id = uuid.uuid4().hex
        self.callchain_id = callchain_id
        if model_name is not None:
            self.params["model_name"] = model_name
        else:
            self.params["model_name"] = None
        self.params["input"] = input

    def set_text_2_image_params(self, prompt: str, model_name, negative_prompt="", callchain_id=None):
        self.task_type = ComputeTaskType.TEXT_2_IMAGE
        self.create_time = time.time()
        self.task_id = uuid.uuid4().hex
        self.callchain_id = callchain_id
        self.params["prompt"] = prompt
        self.params["negative_prompt"] = negative_prompt
        if model_name is not None:
            self.params["model_name"] = model_name
        else:
            self.params["model_name"] = "v1-5-pruned-emaonly"

    def set_image_2_text_params(self, image_path: str, prompt: str, model_name, negative_prompt="", callchain_id=None):
        self.task_type = ComputeTaskType.IMAGE_2_TEXT
        self.create_time = time.time()
        self.task_id = uuid.uuid4().hex
        self.callchain_id = callchain_id
        self.params["image_path"] = image_path
        if prompt == '':
            self.params["prompt"] = "What's in this image?"
        else:
            self.params["prompt"] = prompt
        self.params["negative_prompt"] = negative_prompt
        if model_name is not None:
            self.params["model_name"] = model_name
        else:
            self.params["model_name"] = "gpt-4-vision-preview"


    def display(self) -> str:
        return f"ComputeTask: {self.task_id} {self.task_type} {self.state}"


class ComputeTaskResult:
    def __init__(self) -> None:
        self.create_time = None
        self.task_id: str = None
        self.callchain_id: str = None
        self.worker_id: str = None
        self.error_str : str = None
        self.result_code: int = ComputeTaskResultCode.OK
        self.result_str: str = None # easy to use,can read from result

        self.result : dict = {}

        self.result_refers: dict = {}
        self.pading_data: bytearray = None


    def set_from_task(self, task: ComputeTask):
        self.task_id = task.task_id
        self.callchain_id = task.callchain_id
        task.result = self


