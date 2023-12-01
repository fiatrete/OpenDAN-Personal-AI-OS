import logging
from typing import Dict

from ..frame.compute_kernel import ComputeKernel
from ..agent.ai_function import AIFunction

logger = logging.getLogger(__name__)


class AsrFunction(AIFunction):
    def __init__(self):
        self.func_id = "speech_to_text"
        self.description = "语音识别，将语音转换为文字"

    def get_name(self) -> str:
        return self.func_id

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "audio_file": {"type": "string", "description": "音频文件路径"},
                "model": {"type": "string", "description": "识别模型", "enum": ["openai-whisper"]},
                "prompt": {"type": "string", "description": "提示语句,可以为None"},
                "response_format": {"type": "string", "description": "返回格式", "enum": ["text", "json", "srt", "verbose_json", "vtt"]},
            }
        }

    async def execute(self, **kwargs) -> str:
        logger.info(f"execute asr function: {kwargs}")

        audio_file = kwargs.get("audio_file")
        model = kwargs.get("model")
        prompt = kwargs.get("prompt")
        response_format = kwargs.get("response_format")
        if response_format is None:
            response_format = "text"

        result = await ComputeKernel.get_instance().do_speech_to_text(audio_file, model, prompt, response_format)
        if result is not None:
            return f"exec speech_to_text Ok. {response_format} is\n```\n{result.result_str}\n```"
        else:
            return "exec speech_to_text failed"

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True

    def is_ready_only(self) -> bool:
        return False
