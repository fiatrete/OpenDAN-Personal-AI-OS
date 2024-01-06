# pylint:disable=E0402
import logging
from typing import Dict

from ..proto.ai_function import *
from ..agent.llm_context import GlobaToolsLibrary
from ..frame.compute_kernel import ComputeKernel

logger = logging.getLogger(__name__)

class AsrFunction(AIFunction):
    def __init__(self):
        self.func_id = "aigc.voice_to_text"
        self.description = "Voice recognition, convert the voice into text"
        self.parameters = ParameterDefine.create_parameters({
                "audio_file": {"type": "string", "description": "Audio file path"},
                "model": {"type": "string", "description": "Recognition model", "enum": ["openai-whisper"]},
                "prompt": {"type": "string", "description": "Prompt statement, can be None"},
                "response_format": {"type": "string", "description": "Return format", "enum": ["text", "json", "srt", "verbose_json", "vtt"]},
            })
        
    def register_function(self):
        GlobaToolsLibrary.get_instance().register_tool_function(self)

    def get_id(self) -> str:
        return self.func_id

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict:
        return self.parameters

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
