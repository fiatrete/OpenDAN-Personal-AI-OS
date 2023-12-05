import os
from typing import Any,List,Dict
from aios import AgentMsg,AgentTodo,AgentPrompt
from aios import SimpleAIFunction, SimpleAIOperation
from aios import SimpleEnvironment

class ShellEnvironment(SimpleEnvironment):
    def __init__(self, workspace: str) -> None:
        super().__init__(workspace)

        operator_param = {
            "command": "command will execute",
        }
        self.add_ai_function(SimpleAIFunction("shell_exec",
                                        "execute shell command in linux bash",
                                        self.shell_exec,operator_param))
        
        #run_code_param = {
        #    "pycode": "python code will execute",
        #}
        #self.add_ai_function(SimpleAIFunction("run_code",
        #                                "execute python code",
        #                                self.run_code,run_code_param))
        

    async def shell_exec(self,command:str) -> str:
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
