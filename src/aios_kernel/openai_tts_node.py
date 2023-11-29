import asyncio
import io
import logging
import os
from asyncio import Queue

from aios_kernel import ComputeNode, ComputeTask, ComputeTaskState, ComputeTaskResult, ComputeTaskType, AIStorage

logger = logging.getLogger(__name__)


class OpenAITTSComputeNode(ComputeNode):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.is_start = False
        self.node_id = "openai_tts_node"
        self.task_queue = Queue()
        self.voice_list = {
            "female": ["nova", "shimmer"],
            "man": ["alloy", "echo", "fable", "onyx"]
        }
        if os.getenv("OPENAI_API_KEY") is not None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        else:
            self.openai_api_key = AIStorage.get_instance().get_user_config().get_value("openai_api_key")

        self.start()

    def start(self):
        if self.is_start is True:
            logger.warn("OpenAITTSComputeNode is already start")
            return
        self.is_start = True

        async def _run_task_loop():
            while True:
                task = await self.task_queue.get()
                try:
                    result = await self._run_task(task)
                    if result is not None:
                        task.state = ComputeTaskState.DONE
                        task.result = result
                except Exception as e:
                    logger.error(f"openai_tts_node run task error: {e}")
                    task.state = ComputeTaskState.ERROR
                    task.result = ComputeTaskResult()
                    task.result.set_from_task(task)
                    task.result.worker_id = self.node_id
                    task.result.result_str = str(e)

        asyncio.create_task(_run_task_loop())

    async def _run_task(self,task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        text = task.params["text"]
        voice_name = task.params["voice_name"]
        if voice_name is None:
            voice_name = "default"
        gender = task.params["gender"]
        if gender is None:
            gender = "female"

        voice_list = self.voice_list[gender]
        voice = voice_list[hash(voice_name)%len(voice_list)]

        model_name = task.params['model_name']
        if model_name is None:
            model_name = 'tts-1'

        client = AsyncOpenAI(api_key=self.openai_api_key)

        response = await client.audio.speech.create(model=model_name, voice=voice, input=text)

        cache = io.BytesIO()
        async for data in await response.aiter_bytes():
            cache.write(data)

        cache.seek(0)

        result = ComputeTaskResult()
        result.set_from_task(task)
        result.worker_id = self.node_id
        result.result = cache.read()
        return result

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"openai_tts_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def get_task_state(self, task_id: str):
        pass

    def display(self) -> str:
        return f"OpenAITTSComputeNode: {self.node_id}"

    def get_capacity(self):
        return 0

    def is_support(self, task: ComputeTask) -> bool:
        if task.task_type == ComputeTaskType.TEXT_2_VOICE:
            if task.params['model_name'] is None or task.params['model_name'] == 'tts-1' or task.params['model_name'] == 'tts-1-hd':
                return True
        return False


    def is_local(self) -> bool:
        return False
