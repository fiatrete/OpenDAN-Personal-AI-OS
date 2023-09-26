import os
import io
import asyncio
from asyncio import Queue
import logging
from pathlib import Path

from PIL import Image
from stability_sdk import client
import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation

from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType
from .compute_node import ComputeNode
from .storage import AIStorage, UserConfig

logger = logging.getLogger(__name__)


class Stability_ComputeNode(ComputeNode):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = Stability_ComputeNode()
        return cls._instance

    @classmethod
    def declare_user_config(cls):
        user_config = AIStorage.get_instance().get_user_config()
        user_config.add_user_config(
            "stability_api_key", "stability api key", False, None)
        user_config.add_user_config(
            "stability_model", "stability model name", True, "stable-diffusion-512-v2-1")
        if os.getenv("TEXT2IMG_OUTPUT_DIR") is None:
            home_dir = Path.home()
            output_dir = Path.joinpath(home_dir, "text2img_output")
            Path.mkdir(output_dir, exist_ok=True)
            user_config.add_user_config(
                "text2img_output_dir", "text2image output dir", True, output_dir)
        if os.getenv("STABILITY_DEFAULT_MODEL") is None:
            user_config.add_user_config(
                "stability_default_model", "stability default model", True, "stable-diffusion-512-v2-1")

    def __init__(self):
        super().__init__()

        self.is_start = False
        self.node_id = "stability_node"
        self.api_key = ""
        self.default_model = ""

        self.task_queue = Queue()

    async def initial(self):
        if os.getenv("STABILITY_API_KEY") is not None:
            self.api_key = os.getenv("STABILITY_API_KEY")
        else:
            self.api_key = AIStorage.get_instance(
            ).get_user_config().get_value("stability_api_key")

        if self.api_key is None:
            logger.error("stability api key is None!")
            return False

        # Check out the following link for a list of available engines: https://platform.stability.ai/docs/features/api-parameters#engine
        if os.getenv("STABILITY_DEFAULT_MODEL") is not None:
            self.default_model = os.getenv("STABILITY_DEFAULT_MODEL")
        else:
            self.default_model = AIStorage.get_instance().get_user_config().get_value("stability_default_model")
        
        if self.default_model is None:
            self.default_model = "stable-diffusion-512-v2-1"

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
        logger.info(f"stability_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        model_name = task.params["model_name"]
        prompt = task.params["prompt"]

        logging.info(f"call stability {self.default_model} prompts: {prompt}")

        api = None
        try:
            api = client.StabilityInference(
                key=self.api_key,
                verbose=True,  # Print debug messages.
                engine=model_name,
            )
        except Exception as e:
            task.error_str = f"create stability client failed: {e}"
            logging.warn(task.error_str)
            task.state = ComputeTaskState.ERROR
            return None

        answers = api.generate(
            prompt=prompt,
            # If a seed is provided, the resulting generated image will be deterministic.
            seed=0,
            # What this means is that as long as all generation parameters remain the same, you can always recall the same image simply by generating it again.
            # Note: This isn't quite the case for Clip Guided generations, which we'll tackle in a future example notebook.
            # Amount of inference steps performed on image generation. Defaults to 30.
            steps=30,
            # Influences how strongly your generation is guided to match your prompt.
            cfg_scale=7.0,
            # Setting this value higher increases the strength in which it tries to match your prompt.
            # Defaults to 7.0 if not specified.
            width=512,  # Generation width, defaults to 512 if not included.
            height=512,  # Generation height, defaults to 512 if not included.
            # Number of images to generate, defaults to 1 if not included.
            samples=1,
            # Choose which sampler we want to denoise our generation with.
            sampler=generation.SAMPLER_K_DPMPP_2M
            # Defaults to k_dpmpp_2m if not specified. Clip Guidance only supports ancestral samplers.
            # (Available Samplers: ddim, plms, k_euler, k_euler_ancestral, k_heun, k_dpm_2, k_dpm_2_ancestral, k_dpmpp_2s_ancestral, k_lms, k_dpmpp_2m, k_dpmpp_sde)
        )

        for resp in answers:
            for artifact in resp.artifacts:
                if artifact.finish_reason == generation.FILTER:
                    err_msg = "request activated the API's safety filters"
                    logging.warn(err_msg)
                    task.error_str = err_msg
                    task.state = ComputeTaskState.ERROR
                    return None
                if artifact.type == generation.ARTIFACT_IMAGE:
                    img = Image.open(io.BytesIO(artifact.binary))
                    # Save our generated images with the task_id as the filename.
                    file_name = os.path.join(self.output_dir, task.task_id + ".png")
                    img.save(file_name)

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
                logger.info("stability_node is waiting for task...")
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
