# aiso shell like bash of linux
from .workflow import ai_workflow


class aios_shell:
    def __init__(self,username:str) -> None:
        pass

    async def send_msg(self,msg:str,target_workflow:str) -> str:
        pass

    async def install_workflow(self,workflow_id:ai_workflow) -> None:
        pass
    