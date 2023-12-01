import io
import json
from asyncio import Queue
import asyncio
import openai
import os
import logging
import srt
import webvtt

from openai import AsyncOpenAI
from openai.cli._progress import BufferReader
from pydub import AudioSegment
from datetime import timedelta

from aios import AIStorage,ComputeNode,ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType

logger = logging.getLogger(__name__)

SECONDS_IN_HOUR = 3600
SECONDS_IN_MINUTE = 60
HOURS_IN_DAY = 24
MICROSECONDS_IN_MILLISECOND = 1000

def timedelta_to_vtt_timestamp(timedelta_timestamp):
    hrs, secs_remainder = divmod(timedelta_timestamp.seconds, SECONDS_IN_HOUR)
    hrs += timedelta_timestamp.days * HOURS_IN_DAY
    mins, secs = divmod(secs_remainder, SECONDS_IN_MINUTE)
    msecs = timedelta_timestamp.microseconds // MICROSECONDS_IN_MILLISECOND
    return "%02d:%02d:%02d.%03d" % (hrs, mins, secs, msecs)


class WhisperComputeNode(ComputeNode):
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self.is_start = False
        self.node_id = "whisper_node"
        self.enable = True
        self.task_queue = Queue()

        if os.getenv("OPENAI_API_KEY") is not None:
            self.openai_api_key = os.getenv("OPENAI_API_KEY")
        else:
            self.openai_api_key = AIStorage.get_instance().get_user_config().get_value("openai_api_key")

        self.start()

    def start(self):
        if self.is_start is True:
            logger.warn("WhisperComputeNode is already start")
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
                    logger.error(f"whisper_node run task error: {e}")
                    logger.exception(e)
                    task.state = ComputeTaskState.ERROR
                    task.result = ComputeTaskResult()
                    task.result.set_from_task(task)
                    task.result.worker_id = self.node_id
                    task.result.result_str = str(e)

        asyncio.create_task(_run_task_loop())

    async def _run_task(self, task: ComputeTask):
        task.state = ComputeTaskState.RUNNING
        prompt = task.params["prompt"]
        response_format = None
        if "response_format" in task.params:
            response_format = task.params["response_format"]
        temperature = None
        if "temperature" in task.params:
            temperature = task.params["temperature"]
        language = None
        if "language" in task.params:
            language = task.params["language"]
        file = task.params["file"]

        client = AsyncOpenAI(api_key=self.openai_api_key)

        if os.path.getsize(file) > 25 * 1024 * 1024:
            audio = AudioSegment.from_file(file)
            text = ""
            results = []
            latest_resp = None
            step = 10 * 60 * 1000
            for i in range(0, len(audio), step):
                if i + step < len(audio):
                    chunk = audio[i:i + step]
                else:
                    chunk = audio[i:]
                seg_file = io.BytesIO()
                chunk.export(seg_file, format="mp3")
                seg_file.seek(0)

                resp = await client.audio.transcriptions.create(model="whisper-1",
                                                   file = ("test.mp3", seg_file),
                                                   language=language,
                                                   temperature=temperature,
                                                   prompt=prompt,
                                                   response_format=response_format)
                if response_format == "json":
                    if text == "":
                        text = resp.text
                    else:
                        text += "," + resp.text
                elif response_format == "text":
                    if text == "":
                        text = resp
                    else:
                        text += "," + resp
                elif response_format == "verbose_json":
                    if text == "":
                        text = resp.text
                    else:
                        text += "," + resp.text
                    results.extend(resp.segments)
                elif response_format == "srt":
                    srt_list = list(srt.parse(resp))
                    for item in srt_list:
                        item.start += timedelta(milliseconds=i)
                        item.end += timedelta(milliseconds=i)
                        results.append(item)
                elif response_format == "vtt":
                    vtt = webvtt.read_buffer(io.StringIO(resp))
                    for caption in vtt.captions:
                        start = timedelta_to_vtt_timestamp(
                            srt.srt_timestamp_to_timedelta(caption.start) + timedelta(milliseconds=i))
                        end = timedelta_to_vtt_timestamp(
                            srt.srt_timestamp_to_timedelta(caption.end) + timedelta(milliseconds=i))
                        results.append(webvtt.Caption(start, end, caption.text))
                else:
                    raise Exception(f"not support response_format: {response_format}")

                latest_resp = resp

            result = ComputeTaskResult()
            result.set_from_task(task)
            result.worker_id = self.node_id
            if response_format == "text":
                result.result_str = text
                result.result = text
            elif response_format == "json":
                result.result_str = json.dumps({"text": text})
                resp.text = text
                result.result = resp
            elif response_format == "verbose_json":
                result.result_str = json.dumps({"text": text, "segments": results})
                latest_resp.text = text
                latest_resp.segments = results
                result.result = latest_resp
            elif response_format == "srt":
                result.result_str = srt.compose(results)
                result.result = result.result_str
            elif response_format == "vtt":
                vtt = webvtt.WebVTT()
                vtt.captions.extend(results)
                f = io.StringIO()
                vtt.write(f)
                f.seek(0)
                result.result_str = f.read()
                result.result = result.result_str
            return result
        else:
            with open(file, "rb") as file_reader:
                buffer_reader = BufferReader(file_reader.read(), desc="Upload progress")

            resp = await client.audio.transcriptions.create(model="whisper-1",
                                               file = (file, buffer_reader),
                                               language=language,
                                               temperature=temperature,
                                               prompt=prompt,
                                               response_format=response_format)
            result = ComputeTaskResult()
            result.set_from_task(task)
            result.worker_id = self.node_id
            if response_format == "json":
                result.result_str = json.dumps({"text": resp.text})
            elif response_format == "verbose_json":
                result.result_str = json.dumps({"text": resp.text, "segments": resp.segments})
            elif response_format == "srt" or response_format == "vtt" or response_format == "text":
                result.result_str = resp
            else:
                raise Exception(f"not support response_format: {response_format}")
            result.result = resp
            return result

    async def push_task(self, task: ComputeTask, proiority: int = 0):
        logger.info(f"whisper_node push task: {task.display()}")
        self.task_queue.put_nowait(task)

    async def remove_task(self, task_id: str):
        pass

    def get_task_state(self, task_id: str):
        pass

    def display(self) -> str:
        return f"WhisperComputeNode: {self.node_id}"

    def get_capacity(self):
        return 0

    def is_support(self, task: ComputeTask) -> bool:
        if task.task_type == ComputeTaskType.VOICE_2_TEXT:
            if task.params['model_name'] is None or task.params['model_name'] == 'openai-whisper':
                return True
        return False

    def is_local(self) -> bool:
        return False
