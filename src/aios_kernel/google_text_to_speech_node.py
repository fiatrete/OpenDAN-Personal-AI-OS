
import os
import asyncio
from asyncio import Queue
import logging

from google.cloud import texttospeech

from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType
from .compute_node import ComputeNode

logger = logging.getLogger(__name__)


"""
You need to set the GOOGLE_APPLICATION_CREDENTIALS environment variable when using it.
see:https://cloud.google.com/text-to-speech/docs/before-you-begin
"""


class GoogleTextToSpeechNode(ComputeNode):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(GoogleTextToSpeechNode, cls).__new__(cls)
            cls._instance.is_start = False
        return cls._instance

    def __init__(self):
        super().__init__()
        if self.is_start is True:
            logger.warn("GoogleTextToSpeechNode is already start")
            return

        self.is_start = True
        self.node_id = "google_text_to_speech_node"
        self.task_queue = Queue()

        self.client = texttospeech.TextToSpeechClient()

        self.start()

    def start(self):
        async def _run_task_loop():
            while True:
                task = await self.task_queue.get()
                try:
                    result = self._run_task(task)
                    if result is not None:
                        task.state = ComputeTaskState.DONE
                        task.result = result
                except Exception as e:
                    logger.error(f"google_text_to_speech_node run task error: {e}")
                    task.state = ComputeTaskState.ERROR
                    task.result = ComputeTaskResult()
                    task.result.set_from_task(task)
                    task.result.worker_id = self.node_id
                    task.result.result_str = str(e)

        asyncio.create_task(_run_task_loop())

    def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        language_code = task.params["language_code"]
        text = task.params["text"]

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(language_code=language_code,
                                                  ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)

        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

        response = self.client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

        result = ComputeTaskResult()
        result.set_from_task(task)
        result.worker_id = self.node_id
        result.result = response.audio_content
        return result

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"google_text_to_speech_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def get_task_state(self, task_id: str):
        pass

    def display(self) -> str:
        return f"GoogleTextToSpeechNode: {self.node_id}"

    def get_capacity(self):
        return 0

    def is_support(self, task_type: ComputeTaskType) -> bool:
        if task_type == ComputeTaskType.TEXT_2_VOICE:
            return True
        return False

    def is_local(self) -> bool:
        return False
