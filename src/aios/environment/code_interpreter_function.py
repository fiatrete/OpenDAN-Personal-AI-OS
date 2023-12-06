from typing import Dict

from ..proto.ai_function import *
from .code_interpreter import execute_code


class CodeInterpreterFunction(AIFunction):
    def __init__(self):
        self.func_id = "code_interpreter"
        self.description = "execute python code"

    def get_name(self) -> str:
        return self.func_id

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "python code"}
            }
        }

    async def execute(self, **kwargs) -> str:
        code = kwargs.get("code")
        ret_code, result = execute_code(code=code)
        if ret_code == 0:
            return result.strip()
        else:
            return result.strip()

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True

    def is_ready_only(self) -> bool:
        return False
