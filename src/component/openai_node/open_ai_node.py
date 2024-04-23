import asyncio
import openai
from openai import AsyncOpenAI
import os
import asyncio
from asyncio import Queue
import logging
import json
import aiohttp
import base64
import requests
from openai._types import NOT_GIVEN

from aios import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType,ComputeTaskResultCode,ComputeNode,AIStorage,UserConfig
from aios import image_utils

logger = logging.getLogger(__name__)


class OpenAI_ComputeNode(ComputeNode):
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = OpenAI_ComputeNode()
        return cls._instance

    @classmethod
    def declare_user_config(cls):
        if os.getenv("OPENAI_API_KEY") is None:
            user_config = AIStorage.get_instance().get_user_config()
            user_config.add_user_config("openai_api_key","openai api key",False,None)

    def __init__(self) -> None:
        super().__init__()

        self.is_start = False
        # openai.organization = "org-AoKrOtF2myemvfiFfnsSU8rF" #buckycloud
        self.openai_api_key = None
        self.node_id = "openai_node"
        self.task_queue = Queue()


    async def initial(self):
        if os.getenv("OPENAI_API_KEY") is not None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        else:
            self.openai_api_key = AIStorage.get_instance().get_user_config().get_value("openai_api_key")

        if self.openai_api_key is None:
            logger.error("openai_api_key is None!")
            return False

        openai.api_key = self.openai_api_key
        self.start()
        return True

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"openai_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def message_to_dict(self, message)->dict:
        result = message.dict()
        # result_msg = {}
        # #message.json()
        # if message.content:
        #     result_msg["content"] = message.content
        # result_msg["role"] = message.role
        # if message.function_call:
        #     function_call = {}
        #     function_call["arguments"] = message.function_call.arguments
        #     function_call["name"] = message.function_call.name
        #     result_msg["function_call"] = function_call

        # if message.tool_calls:
        #     tool_calls = []
        #     for tool_call in message.tool_calls:
        #         tool_call_dict = {}
        #         tool_call_dict["id"] = tool_call.id
        #         tool_call_dict["type"] = tool_call.type
        #         func_call_dict = {}
        #         func_call_dict["name"] = tool_call.function.name
        #         func_call_dict["arguments"] = tool_call.function.arguments
        #         tool_call_dict["function"] = func_call_dict

        #         tool_calls.append(tool_call_dict)
        #     result_msg["tool_calls"] = message.tool_calls

        # result["message"] = result_msg
        return result

    def _image_2_text(self, task: ComputeTask):
        logger.info('openai image_2_text')
        # 本地图片处理

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key }"
        }
        model_name = task.params["model_name"]
        image_path = task.params["image_path"]

        if image_utils.is_file(image_path):
            url = image_utils.to_base64(image_path, (1024, 1024))
        else:
            url = image_path

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": task.params["prompt"]
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": url
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 300
        }
        logger.info('openai send image_2_text request ')
        # openai 的库的Vision只支持传图片的url地址。本地图片得用request
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        if response.status_code == 200:
            logger.info('openai image_2_text success')
            return response.json()
        else:
            logger.error('openai image_2_text error')
            logger.error(response.json())
            return None

    async def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING

        result = ComputeTaskResult()
        result.result_code = ComputeTaskResultCode.ERROR
        result.set_from_task(task)

        match task.task_type:
            case ComputeTaskType.TEXT_EMBEDDING:
                model_name = task.params["model_name"]
                input = task.params["input"]
                logger.info(f"call openai {model_name} input: {input}")
                try:
                    resp = openai.Embedding.create(model=model_name,
                                                input=input)
                except Exception as e:
                    logger.error(f"openai run TEXT_EMBEDDING task error: {e}")
                    task.state = ComputeTaskState.ERROR
                    task.error_str = str(e)
                    result.error_str = str(e)
                    return result

                # resp = {
                # "object": "list",
                # "data": [
                #     {
                #     "object": "embedding",
                #     "index": 0,
                #     "embedding": [
                #         -0.00930514745414257,
                #         0.00765434792265296,
                #         -0.007167573552578688,
                #         -0.012373941019177437,
                #         -0.04884673282504082
                #     ]}]
                # }

                logger.info(f"openai response: {resp}")
                task.state = ComputeTaskState.DONE
                result.result_code = ComputeTaskResultCode.OK
                result.worker_id = self.node_id
                result.result_str = resp["data"][0]["embedding"]

                return result
            case ComputeTaskType.IMAGE_2_TEXT:
                result.result_code = ComputeTaskResultCode.OK
                result.worker_id = self.node_id
                # result.result_str = resp["data"][0]["image_2_text"]
                result.result["message"] = self._image_2_text(task)
                return result
            case ComputeTaskType.LLM_COMPLETION:
                mode_name = task.params["model_name"]
                prompts = task.params["prompts"]
                resp_mode = task.params["resp_mode"]
                if resp_mode == "json":
                    response_format = { "type": "json_object" }
                else:
                    response_format = None
                max_token_size = task.params.get("max_token_size")
                llm_inner_functions = task.params.get("inner_functions")
                if max_token_size is None:
                    max_token_size = 4000

                if mode_name == "gpt-4-vision-preview":
                    response_format = NOT_GIVEN
                    llm_inner_functions = None
                    if max_token_size > 4096 or max_token_size < 50:
                        result_token = 4096
                    else:
                        result_token = -1
                else:
                    result_token = NOT_GIVEN

                client = AsyncOpenAI(api_key=self.openai_api_key)
                try:
                    if llm_inner_functions is None or len(llm_inner_functions) == 0:
                        if mode_name != "gpt-4-vision-preview":
                            logger.info(f"call openai {mode_name} prompts: {prompts}")
                        resp = await client.chat.completions.create(model=mode_name,
                                                        messages=prompts,
                                                        response_format = response_format,
                                                        max_tokens=result_token,
                                                        )
                    else:
                        if mode_name != "gpt-4-vision-preview":
                            logger.info(f"call openai {mode_name} prompts: \n\t {prompts} \nfunctions: \n\t{json.dumps(llm_inner_functions,ensure_ascii=False)}")
                        resp = await client.chat.completions.create(model=mode_name,
                                                            messages=prompts,
                                                            response_format = response_format,
                                                            functions=llm_inner_functions,
                                                            max_tokens=result_token,
                                                            ) # TODO: add temperature to task params?
                except Exception as e:
                    logger.error(f"openai run LLM_COMPLETION task error: {e}")
                    task.state = ComputeTaskState.ERROR
                    task.error_str = str(e)
                    result.error_str = str(e)
                    return result

                #logger.info(f"openai response: {resp}")
                #TODO: gpt-4v api is image_2_text ?
                if mode_name == "gpt-4-vision-preview":
                    status_code = resp.choices[0].finish_reason
                    if status_code is None:
                        status_code = resp.choices[0].finish_details['type']
                else:
                    status_code = resp.choices[0].finish_reason
                token_usage = resp.usage

                match status_code:
                    case "function_call":
                        task.state = ComputeTaskState.DONE
                    case "stop":
                        task.state = ComputeTaskState.DONE
                    case _:
                        task.state = ComputeTaskState.ERROR
                        task.error_str = f"The status code was {status_code}."
                        result.error_str = f"The status code was {status_code}."
                        result.result_code = ComputeTaskResultCode.ERROR
                        return result

                result.result_code = ComputeTaskResultCode.OK
                result.worker_id = self.node_id
                result.result_str = resp.choices[0].message.content

                result.result["message"] = self.message_to_dict(resp.choices[0].message)

                if token_usage:
                    result.result_refers["token_usage"] = token_usage

                logger.info(f"openai success response: {result.result_str}")
                return result
            case _:
                task.state = ComputeTaskState.ERROR
                task.error_str = f"ComputeTask's TaskType : {task.task_type} not support!"
                result.error_str = f"ComputeTask's TaskType : {task.task_type} not support!"
                return None

    def start(self):
        if self.is_start is True:
            return
        self.is_start = True

        async def _run_task_loop():
            while True:
                task = await self.task_queue.get()
                logger.info(f"openai_node get task: {task.display()}")
                result = await self._run_task(task)
                if result is not None:
                    task.result = result
                    task.state = ComputeTaskState.DONE

        asyncio.create_task(_run_task_loop())

    def display(self) -> str:
        return f"OpenAI_ComputeNode: {self.node_id}"

    def get_task_state(self, task_id: str):
        pass

    def get_capacity(self):
        pass


    def is_support(self, task: ComputeTask) -> bool:
        if task.task_type == ComputeTaskType.LLM_COMPLETION:
            if not task.params["model_name"]:
                return True
            model_name : str = task.params["model_name"]
            if model_name.startswith("gpt-"):
                return True

        if task.task_type == ComputeTaskType.IMAGE_2_TEXT:
            model_name : str = task.params["model_name"]
            if model_name.startswith("gpt-4"):
                return True
        #if task.task_type == ComputeTaskType.TEXT_EMBEDDING:
        #    if task.params["model_name"] == "text-embedding-ada-002":
        #        return True
        return False


    def is_local(self) -> bool:
        return False
