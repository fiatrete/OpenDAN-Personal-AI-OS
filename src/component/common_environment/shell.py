import os
from typing import Any,List,Dict
from aios import SimpleAIFunction
from aios import SimpleEnvironment
from aios import GlobaToolsLibrary,ParameterDefine

class ShellEnvironment(SimpleEnvironment):
    def __init__(self) -> None:
        super().__init__("shell")

    @classmethod
    def register_global_functions(cls):
        operator_param = ParameterDefine.create_parameters({"command":"command will execute"})
        GlobaToolsLibrary.get_instance().register_tool_function(SimpleAIFunction("system.shell.exec",
                                        "execute shell command in linux bash",
                                        ShellEnvironment.shell_exec,operator_param))
    @staticmethod
    async def shell_exec(command:str) -> str:
        import asyncio.subprocess
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        returncode = process.returncode
        if returncode == 0:
            return f"Execute success! stdout is:\n{stdout}\n"
        else:
            return f"Execute failed! stderr is:\n{stderr}\n"
