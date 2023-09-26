
import os
import asyncio
from asyncio import Queue
import logging
from typing import Optional

from google.cloud import texttospeech

from .storage import AIStorage
from .compute_task import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType
from .compute_node import ComputeNode

logger = logging.getLogger(__name__)


"""
You need to set the GOOGLE_APPLICATION_CREDENTIALS environment variable when using it.
see:https://cloud.google.com/text-to-speech/docs/before-you-begin
"""


class GoogleTextToSpeechNode(ComputeNode):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.node_id = "google_text_to_speech_node"
        self.task_queue = Queue()
        self.client: Optional[texttospeech.TextToSpeechClient] = None

        self.language_list = {
            "cnm-CN": {
                "female": ["cmn-CN-Standard-A",
                           "cmn-CN-Standard-D",
                           "cmn-CN-Wavenet-A",
                           "cmn-CN-Wavenet-D",
                           "cmn-TW-Standard-A",
                           "cmn-TW-Wavenet-A"],
                "man": ["cmn-CN-Standard-B",
                        "cmn-CN-Standard-C",
                        "cmn-CN-Wavenet-B",
                        "cmn-CN-Wavenet-C",
                        "cmn-TW-Standard-B",
                        "cmn-TW-Standard-C",
                        "cmn-TW-Wavenet-B",
                        "cmn-TW-Wavenet-C"]
            },
            "en-US": {
                "female": ["en-US-Neural2-C",
                           "en-US-Neural2-E",
                           "en-US-Neural2-F",
                           "en-US-Neural2-G",
                           "en-US-Neural2-H",
                           "en-US-News-K",
                           "en-US-News-L",
                           "en-US-Standard-C",
                           "en-US-Standard-E",
                           "en-US-Standard-F",
                           "en-US-Standard-G",
                           "en-US-Standard-H",
                           "en-US-Studio-O",
                           "en-US-Wavenet-C",
                           "en-US-Wavenet-E",
                           "en-US-Wavenet-F",
                           "en-US-Wavenet-G",
                           "en-US-Wavenet-H"],
                "man": ["en-US-Polyglot-1",
                        "en-US-Standard-A",
                        "en-US-Standard-B",
                        "en-US-Standard-D",
                        "en-US-Standard-I",
                        "en-US-Standard-J",
                        "en-US-Studio-M",
                        "en-US-Wavenet-A",
                        "en-US-Wavenet-B",
                        "en-US-Wavenet-D",
                        "en-US-Wavenet-I",
                        "en-US-Wavenet-J"]
            }
        }
        self.start()

    def init(self):
        user_config = AIStorage.get_instance().get_user_config()
        google_application_credentials = user_config.get_value("google_application_credentials")
        if google_application_credentials is None:
            raise Exception("google_application_credentials is None!")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_application_credentials
        self.client = texttospeech.TextToSpeechClient()

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
        voice_name = task.params["voice_name"]
        gender = task.params["gender"]
        age = task.params["age"]

        if language_code == "zh":
            language_code = "cnm-CN"
        elif language_code == "en":
            language_code = "en-US"
        else:
            raise Exception(f"language_code {language_code} not support")

        lang_list = self.language_list[language_code][gender]
        voice = lang_list[hash(voice_name) % len(lang_list)]

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(language_code=language_code,
                                                  ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL,
                                                  name=voice)

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

    def is_support(self, task: ComputeTask) -> bool:
        if task.task_type == ComputeTaskType.TEXT_2_VOICE:
            return True
        return False

    def is_local(self) -> bool:
        return False

    def declare_user_config(self):
        if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") is None:
            user_config = AIStorage.get_instance().get_user_config()
            user_config.add_user_config("google_application_credentials",
                                        "google application credentials, please visit:https://cloud.google.com/text-to-speech/docs/before-you-begin",
                                        True,
                                        None)
