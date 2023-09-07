import os
import io
import asyncio
from asyncio import Queue
import logging

from PIL import Image
from stability_sdk import client
import stability_sdk.interfaces.gooseai.generation.generation_pb2 as generation

from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType
from .compute_node import ComputeNode

logger = logging.getLogger(__name__)


class Stability_ComputeNode(ComputeNode):
    _instanace = None

    def __new__(cls):
        if cls._instanace is None:
            cls._instanace = super(Stability_ComputeNode, cls).__new__(cls)
            cls._instanace.is_start = False
        return cls._instanace

    def __init__(self) -> None:
        super().__init__()
        if self.is_start is True:
            logger.warn("Stability_ComputeNode is already start")
            return

        self.is_start = True
        self.node_id = "stability_node"
        self.api_key = ""  # "sk-RQDlJtBFQg6I3IueeGCGZTPhWPYAl3bgRdvFDMkcEXsKbUc0"
        self.engine = ""  # stable-diffusion-512-v2-0

        self.task_queue = Queue()

        if os.getenv("STABILITY_API_KEY") is not None:
            self.api_key = os.getenv("STABILITY_API_KEY")
        else:
            self.api_key = "sk-RQDlJtBFQg6I3IueeGCGZTPhWPYAl3bgRdvFDMkcEXsKbUc0"

        # Check out the following link for a list of available engines: https://platform.stability.ai/docs/features/api-parameters#engine
        if os.getenv("STABILITY_ENGINE") is not None:
            self.engine = os.getenv("STABILITY_ENGINE")
        else:
            self.engine = "stable-diffusion-512-v2-1"

        self.client = client.StabilityInference(
            key=self.api_key,
            verbose=True,  # Print debug messages.
            engine=self.engine,
        )

        self.start()

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"stability_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        # model_name && max_token_size not used here
        prompts = task.params["prompts"]

        logging.info(f"call stability {self.engine} prompts: {prompts}")
        answers = self.client.generate(
            prompt=prompts,
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
                logger.info("artifact:", artifact.id,
                            artifact.type, artifact.finish_reason)
                if artifact.finish_reason == generation.FILTER:
                    logging.warn("request activated the API's safety filters")
                if artifact.type == generation.ARTIFACT_IMAGE:
                    img = Image.open(io.BytesIO(artifact.binary))
                    # Save our generated images with the task_id as the filename.
                    file_name = task.task_id + ".png"  # which dir to save?
                    img.save(file_name)

                    result = ComputeTaskResult()
                    result.set_from_task(task)
                    result.worker_id = self.node_id
                    result.result = {"file": file_name}

                    return result

        return None

    def start(self):
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

    def is_support(self, task_type: ComputeTaskType) -> bool:
        return task_type == ComputeTaskType.TEXT_2_IMAGE

    def is_local(self) -> bool:
        return False
