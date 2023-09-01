from enum import Enum
import uuid
import time 
import re

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
    
    @classmethod
    def parse_function_call(cls,func_string:str):
        match = re.search(r'\s*(\w+)\s*\(\s*(.*)\s*\)\s*', func_string)
        if not match:
            return None

        func_name = match.group(1)
        if func_name is None:
            return None
        if len(func_name) < 2:
            return None
        
        params_string = match.group(2).strip()    
        params = re.split(r'\s*,\s*(?=(?:[^"]*"[^"]*")*[^"]*$)', params_string)
        params = [param.strip('"') for param in params]

        return func_name, params
        
