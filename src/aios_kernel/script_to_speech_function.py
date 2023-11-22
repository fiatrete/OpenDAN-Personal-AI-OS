import io
import logging
import os
import random
from pathlib import Path
from typing import Dict

from aios_kernel import ComputeKernel, AIStorage
from aios_kernel.ai_function import AIFunction

from pydub import AudioSegment

logger = logging.getLogger(__name__)


class ScriptToSpeechFunction(AIFunction):
    def __init__(self):
        self.func_id = "script_to_speech"
        self.description = "根据输入的剧本生成音频文件，成功时会返回音频文件路径"
        self.speech_path = os.path.join(AIStorage.get_instance().get_myai_dir(), "tts")
        Path(self.speech_path).mkdir(exist_ok=True)

    def get_name(self) -> str:
        return self.func_id

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "language": {"type": "string", "description": "演播语言", "enum": ["zh", "en"]},
                "model": {"type": "string", "description": "演播模型", "enum": ["tts-1", "tts-1-hd"]},
                "roles": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "角色名字"},
                        "gender": {"type": "string", "description": "角色性别", "enum": ["man", "female"]},
                        "age": {"type": "string", "description": "年龄", "enum": ["child", "adult"]},
                    }}},
                "lines": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "角色名字"},
                        "tone": {"type": "string", "description": "演播情感",
                                 "enum": ["happy", "sad", "angry", "fear", "disgust", "surprise", "neutral"]},
                        "text": {"type": "string", "description": "台词"},
                    }
                }}
            }
        }

    async def execute(self, **kwargs) -> str:
        logger.info(f"execute text_to_speech function: {kwargs}")

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
                    logger.error(f"do_text_to_speech failed: {e}")
                    i += 1
                    continue

        if audio is not None:
            path = os.path.join(self.speech_path, "{}.mp3".format(''.join(random.sample('zyxwvutsrqponmlkjihgfedcba', 10))))
            audio.export(path, format="mp3")
            return "exec text_to_speech OK，speech file store at ```{}```".format(path)
        else:
            return "exec text_to_speech failed"

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True

    def is_ready_only(self) -> bool:
        return False


