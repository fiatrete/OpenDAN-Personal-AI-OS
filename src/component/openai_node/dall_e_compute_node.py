import os
import io
import asyncio
from asyncio import Queue
import logging
from pathlib import Path
from openai import OpenAI
import base64

from PIL import Image

from aios import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType, ComputeTaskResultCode,ComputeNode, AIStorage, UserConfig

logger = logging.getLogger(__name__)


class DallE_ComputeNode(ComputeNode):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = DallE_ComputeNode()
        return cls._instance

    @classmethod
    def declare_user_config(cls):
        user_config = AIStorage.get_instance().get_user_config()

        if os.getenv("TEXT2IMG_OUTPUT_DIR") is None:
            home_dir = Path.home()
            output_dir = Path.joinpath(home_dir, "text2img_output")
            Path.mkdir(output_dir, exist_ok=True)
            user_config.add_user_config(
                "text2img_output_dir", "text2image output dir", True, output_dir)

    def __init__(self):
        super().__init__()

        self.is_start = False
        self.node_id = "dall_e_node"
        self.openai_api_key = ""
        self.default_model = "dall-e-3"

        self.task_queue = Queue()

    async def initial(self):
        if os.getenv("OPENAI_API_KEY") is not None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        else:
            self.openai_api_key = AIStorage.get_instance().get_user_config().get_value("openai_api_key")

        if self.openai_api_key is None:
            logger.error("openai_api_key is None!")
            return False

        if os.getenv("TEXT2IMG_OUTPUT_DIR") is not None:
            self.output_dir = os.getenv("TEXT2IMG_OUTPUT_DIR")
        else:
            self.output_dir = AIStorage.get_instance(
            ).get_user_config().get_value("text2img_output_dir")

        if self.output_dir is None:
            self.output_dir = "./"
            self.output_dir = os.path.abspath(self.output_dir)

        self.start()

        return True

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"DallE_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        result = ComputeTaskResult()
        result.result_code = ComputeTaskResultCode.ERROR
        result.set_from_task(task)

        try:
            prompt = task.params["prompt"]
            logging.info(f"Call DallE {self.default_model} prompts: {prompt}")
            client = OpenAI(api_key=self.openai_api_key)

            response = client.images.generate(
                model=self.default_model,
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
                response_format="b64_json",
            )

            binary_data = base64.b64decode(response.data[0].b64_json)
            image = Image.open(io.BytesIO(binary_data))
            file_name = os.path.join(self.output_dir, task.task_id + ".png")
            image.save(file_name)
            
            task.state = ComputeTaskState.DONE
            result.result_code = ComputeTaskResultCode.OK
            result.worker_id = self.node_id
            result.result = {"file": file_name}

            return result
        
        except Exception as e:
            logging.error(f"Call DallE failed. err: {e}")
            task.error_str = str(e)
            result.error_str = str(e)
            task.state = ComputeTaskState.ERROR
            return result

    async def start(self):
        if self.is_start:
            return
        self.is_start = True

        async def _run_task_loop():
            while True:
                logger.info("Dall E node is waiting for task...")
                task = await self.task_queue.get()
                logger.info(f"Dall E node get task: {task.display()}")
                result = self._run_task(task)

        asyncio.create_task(_run_task_loop())

    def display(self) -> str:
        return f"DallE_ComputeNode: {self.node_id}"

    def get_task_state(self, task_id: str):
        pass

    def get_capacity(self):
        pass

    def is_support(self, task: ComputeTask) -> bool:
        return task.task_type == ComputeTaskType.TEXT_2_IMAGE

    def is_local(self) -> bool:
        return False
