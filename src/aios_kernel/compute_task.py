
from enum import Enum
import uuid
import time
from typing import Union
from knowledge import ObjectID
from .storage import AIStorage

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
    TEXT_2_IMAGE = "text_2_image"
    IMAGE_2_TEXT = "image_2_text"
    IMAGE_2_IMAGE = "image_2_image"
    VOICE_2_TEXT = "voice_2_text"
    TEXT_2_VOICE = "text_2_voice"
    TEXT_EMBEDDING ="text_embedding"
    IMAGE_EMBEDDING ="image_embedding"


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
        self.result_code: int = 0
        self.result_str: str = None # easy to use,can read from result

        self.result : dict = {}

        self.result_refers: dict = {}
        self.pading_data: bytearray = None
        

    def set_from_task(self, task: ComputeTask):
        self.task_id = task.task_id
        self.callchain_id = task.callchain_id
        task.result = self
