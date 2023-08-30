from enum import Enum
import uuid
import time 

class AgentMsgState(Enum):
    RESPONSED = 0
    INIT = 1
    SENDING = 2
    PROCESSING = 3
    ERROR = 4

class AgentMsg:
    def __init__(self) -> None:
        self.create_time = 0
        self.sender:str = None
        self.target:str = None
        self.body:str = None
        self.topic:str = "T#" + uuid.uuid4().hex
        #self.msg_type = 0
        self.state = AgentMsgState.INIT
        self.resp_msg = None

    def set(self,sender:str,target:str,body:str,topic:str=None) -> None:
        self.id = "msg#" + uuid.uuid4().hex
        self.sender = sender
        self.target = target
        self.body = body
        self.create_time = time.time()
        if topic:
            self.topic = topic

    def get_msg_id(self) -> str:
        return self.id

    def get_sender(self) -> str:
        return self.sender

    def get_target(self) -> str:
        return self.target
