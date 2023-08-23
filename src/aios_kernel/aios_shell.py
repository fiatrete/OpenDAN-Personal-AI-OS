# aiso shell like bash of linux
from .workflow import Workflow


class AIOS_Shell:
    def __init__(self,username:str) -> None:
        pass

    async def send_msg(self,msg:str,target_workflow:str) -> str:
        pass

    async def install_workflow(self,workflow_id:Workflow) -> None:
        pass
    