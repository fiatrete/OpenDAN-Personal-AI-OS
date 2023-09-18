
from enum import Enum
import uuid
import time


class ComputeTaskState(Enum):
    DONE = 0
    INIT = 1
    RUNNING = 2
    ERROR = 3
    PENDING = 4

class ComputeTaskType(Enum):
    NONE = -1
    LLM_COMPLETION = 0
    TEXT_2_IMAGE = 1
    IMAGE_2_IMAGE = 2
    VOICE_2_TEXT = 3
    TEXT_2_VOICE = 4


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

    def set_llm_params(self, prompts, model_name, max_token_size, inner_functions = None, callchain_id=None):
        self.task_type = ComputeTaskType.LLM_COMPLETION
        self.create_time = time.time()
        self.task_id = uuid.uuid4().hex
        self.callchain_id = callchain_id
        self.params["prompts"] = prompts.messages
        if model_name is not None:
            self.params["model_name"] = model_name
        else:
            self.params["model_name"] = "gpt-4-0613"
        if max_token_size is None:
            self.params["max_token_size"] = 4000
        else:
            self.params["max_token_size"] = max_token_size

        if inner_functions is not None:
            self.params["inner_functions"] = inner_functions

    def set_text_embedding_params(self, input, model_name=None, callchain_id = None):
        self.task_type = "text_embedding"
        self.create_time = time.time()
        self.task_id = uuid.uuid4().hex
        self.callchain_id = callchain_id
        if model_name is not None:
            self.params["model_name"] = model_name
        else:
            self.params["model_name"] = "text-embedding-ada-002"
        self.params["input"] = input

    def display(self) -> str:
        return f"ComputeTask: {self.task_id} {self.task_type} {self.state}"


class ComputeTaskResult:
    def __init__(self) -> None:
        self.create_time = None
        self.task_id: str = None
        self.callchain_id: str = None
        self.worker_id: str = None
        self.result_code: int = 0
        self.result_str: str = None # easy to use,can read from result
        self.result_message: dict = {}
        self.result_refers: dict = None
        self.pading_data: bytearray = None

    def set_from_task(self, task: ComputeTask):
        self.task_id = task.task_id
        self.callchain_id = task.callchain_id
