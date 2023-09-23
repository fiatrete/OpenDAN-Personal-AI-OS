import os
import io
import asyncio
from asyncio import Queue
import logging
import base64
from PIL import Image
import requests
from typing import Tuple

from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType
from .compute_node import ComputeNode
from .storage import AIStorage, UserConfig

logger = logging.getLogger(__name__)


class Local_Stability_ComputeNode(ComputeNode):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Local_Stability_ComputeNode()
        return cls._instance

    @classmethod
    def declare_user_config(cls):
        user_config = AIStorage.get_instance().get_user_config()
        user_config.add_user_config(
            "local_stability_url", "local stability url", False, None)
        user_config.add_user_config(
            "text2img_output_dir", "output dir", True, "./")
        user_config.add_user_config(
            "text2img_default_model", "text2img default model", True, "v1-5-pruned-emaonly")

    def __init__(self) -> None:
        super().__init__()

        self.is_start = False
        self.node_id = "local_stability_node"
        self.url = None
        self.default_model = None
        self.output_dir = None

        self.task_queue = Queue()
    
    async def initial(self):
        if os.getenv("LOCAL_STABILITY_URL") is not None:
            self.url = os.getenv("LOCAL_STABILITY_URL")
        else:
            self.url = AIStorage.get_instance(
            ).get_user_config().get_value("local_stability_url")

        if os.getenv("TEXT2IMG_OUTPUT_DIR") is not None:
            self.output_dir = os.getenv("TEXT2IMG_OUTPUT_DIR")
        else:
            self.output_dir = AIStorage.get_instance(
            ).get_user_config().get_value("text2img_output_dir")
        
        if os.getenv("TEXT2IMG_DEFAULT_MODEL") is not None:
            self.default_model = os.getenv("TEXT2IMG_DEFAULT_MODEL")
        else:
            self.default_model = AIStorage.get_instance(
            ).get_user_config().get_value("text2img_default_model")

        if self.url is None:
            logger.error("local stability url is None!")
            return False

        if self.default_model is None:
            logger.error("local stability default model is None!")
            return False

        if self.output_dir is None:
            self.output_dir = "./"
        
        self.output_dir = os.path.abspath(self.output_dir)

        self.start()

        return True

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"stability_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def _make_post_request(self, url, json) -> Tuple[str, requests.Response]:
        try:
            response = requests.post(url, json=json)
            if response.status_code != 200:
                return f'{response.status_code}, {response.json()}', None
            return None, response
        except Exception as e:
            return f"{e}", None


    def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        model_name = task.params["model_name"]
        prompt = task.params["prompt"]

        logging.info(f"call local stability {model_name} prompts: {prompt}")

        if model_name is not None:
            payload = {
                "sd_model_checkpoint": model_name,
            }
            err, resp = self._make_post_request(f'{self.url}/sdapi/v1/options', payload)

            if err is not None:
                task.state = ComputeTaskState.ERROR
                err_msg = f"Set local stability model failed. err:{err}"
                logger.error(err_msg)
                task.error_str = err_msg
                return None

            logging.info(f"set local stability model {model_name} success")

        payload = {
            "prompt": prompt,
            "steps": 20
        }

        err, resp = self._make_post_request(f'{self.url}/sdapi/v1/txt2img', payload)
        if err is not None:
            task.state = ComputeTaskState.ERROR
            err_msg = f"Failed. err:{err}"
            logger.error(err_msg)
            task.error_str = err_msg
            return None
        
        r = resp.json()

        for i in r['images']:
            image = Image.open(io.BytesIO(
                base64.b64decode(i.split(",", 1)[0])))
            file_name = os.path.join(self.output_dir, task.task_id + ".png")
            image.save(file_name)

            result = ComputeTaskResult()
            result.set_from_task(task)
            result.worker_id = self.node_id
            result.result = {"file": file_name}

            return result

        task.error_str = "Unknown error!"
        task.state = ComputeTaskState.ERROR
        return None

    def start(self):
        if self.is_start:
            return
        self.is_start = True

        async def _run_task_loop():
            while True:
                logger.info("local_stability_node is waiting for task...")
                task = await self.task_queue.get()
                logger.info(f"stability_node get task: {task.display()}")
                result = self._run_task(task)
                if result is not None:
                    task.state = ComputeTaskState.DONE
                    task.result = result

        asyncio.create_task(_run_task_loop())

    def display(self) -> str:
        return f"Stability_ComputeNode: {self.node_id}"

    def get_task_state(self, task_id: str):
        pass

    def get_capacity(self):
        pass

    def is_support(self, task: ComputeTask) -> bool:
        return task.task_type == ComputeTaskType.TEXT_2_IMAGE

    def is_local(self) -> bool:
        return False
