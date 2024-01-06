# pylint:disable=E0402

import io
import logging
import os
import random
from pathlib import Path
from typing import Dict

from ..proto.ai_function import *
from ..frame.compute_kernel import ComputeKernel
from ..storage.storage import AIStorage


from pydub import AudioSegment

logger = logging.getLogger(__name__)


class ScriptToSpeechFunction(AIFunction):
    def __init__(self):
        self.func_id = "aigc.script_to_speech"
        self.description = "Generate audio files according to the input script, and the audio file path will be returned when successful"
        self.speech_path = os.path.join(AIStorage.get_instance().get_myai_dir(), "tts")
        self.parameters = ParameterDefine.create_parameters({
                "language": {"type": "string", "description": "Actual language", "enum": ["zh", "en"]},
                "model": {"type": "string", "description": "Studio", "enum": ["tts-1", "tts-1-hd"]},
                "roles": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Character name"},
                        "gender": {"type": "string", "description": "Gender", "enum": ["man", "female"]},
                        "age": {"type": "string", "description": "age", "enum": ["child", "adult"]},
                    }}},
                "lines": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Character name"},
                        "tone": {"type": "string", "description": "Sovereign emotions",
                                 "enum": ["happy", "sad", "angry", "fear", "disgust", "surprise", "neutral"]},
                        "text": {"type": "string", "description": "Line"},
                    }
                }}
            })
        
        Path(self.speech_path).mkdir(exist_ok=True)

    def get_id(self) -> str:
        return self.func_id

    def get_description(self) -> str:
        return self.description

    def get_parameters(self):
        return self.parameters

    async def execute(self, **kwargs) -> str:
        logger.info(f"execute aigc.script_to_speech function: {kwargs}")

        language = kwargs.get("language")
        if language is None:
            language = "zh"
        model = kwargs.get("model")
        roles = kwargs.get("roles")
        lines = kwargs.get("lines")

        audio = None
        for line in lines:
            name = line.get("name")
            tone = line.get("tone")
            text = line.get("text")
            gender = None
            age = None
            for role in roles:
                role_name = role.get("name")
                if role_name == name:
                    gender = role.get("gender")
                    age = role.get("age")
                    break
            i = 0
            while i < 3:
                try:
                    data = await ComputeKernel.get_instance().do_text_to_speech(text, language, gender, age, name, tone, model_name=model)
                    if audio is None:
                        audio = AudioSegment.from_mp3(io.BytesIO(data))
                    else:
                        audio = audio + AudioSegment.from_mp3(io.BytesIO(data))
                    break
                except Exception as e:
                    logger.error(f"script_to_speech failed: {e}")
                    i += 1
                    continue

        if audio is not None:
            path = os.path.join(self.speech_path, "{}.mp3".format(''.join(random.sample('zyxwvutsrqponmlkjihgfedcba', 10))))
            audio.export(path, format="mp3")
            return "exec script_to_speech OK，speech file store at ```{}```".format(path)
        else:
            return "exec script_to_speech failed"

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True

    def is_ready_only(self) -> bool:
        return False


