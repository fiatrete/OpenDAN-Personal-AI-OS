import json
import logging
import shlex
import uuid
from enum import Enum
import time
from typing import Tuple, List

logger = logging.getLogger(__name__)

class AgentMsgType(Enum):
    TYPE_MSG = 0
    TYPE_GROUPMSG = 1
    TYPE_INTERNAL_CALL = 10
    TYPE_ACTION = 20
    TYPE_EVENT = 30
    TYPE_SYSTEM = 40


class AgentMsgStatus(Enum):
    RESPONSED = 0
    INIT = 1
    SENDING = 2
    PROCESSING = 3
    ERROR = 4
    RECVED = 5
    EXECUTED = 6

# msg is a msg / msg resp
# msg body可以有内容类型（MIME标签），text, image, voice, video, file,以及富文本(html)
# msg is a inner function call with result
# msg is a Action with result

# qutoe Msg
# forword msg
# reply msg

# 逻辑上的同一个Message在同一个session中看到的msgid相同
#       在不同的session中看到的msgid不同

class AgentMsg:
    def __init__(self,msg_type=AgentMsgType.TYPE_MSG) -> None:
        self.msg_id = "msg#" + uuid.uuid4().hex
        self.msg_type:AgentMsgType = msg_type

        self.prev_msg_id:str = None
        self.quote_msg_id:str = None
        self.rely_msg_id:str = None # if not none means this is a respone msg
        self.session_id:str = None

        #forword info


        self.create_time = 0
        self.done_time = 0
        self.topic:str = None # topic is use to find session, not store in db

        self.sender:str = None # obj_id.sub_objid@tunnel_id
        self.target:str = None
        self.mentions:[] = None #use in group chat only
        #self.title:str = None
        self.body:str = None
        self.body_mime:str = None #//default is "text/plain",encode is utf8

        #type is call / action
        self.func_name = None
        self.args = None
        self.result_str = None

        #type is event
        self.event_name = None
        self.event_args = None

        self.status = AgentMsgStatus.INIT
        self.inner_call_chain = []
        self.resp_msg = None

    @classmethod
    def from_json(cls,json_obj:dict) -> 'AgentMsg':
        msg = AgentMsg()

        return msg

    @classmethod
    def create_internal_call_msg(self,func_name:str,args:dict,prev_msg_id:str,caller:str):
        msg = AgentMsg(AgentMsgType.TYPE_INTERNAL_CALL)
        msg.create_time = time.time()
        msg.func_name = func_name
        msg.args = args
        msg.prev_msg_id = prev_msg_id
        msg.sender = caller
        return msg

    def create_action_msg(self,action_name:str,args:dict,caller:str):
        msg = AgentMsg(AgentMsgType.TYPE_ACTION)
        msg.create_time = time.time()
        msg.func_name = action_name
        msg.args = args
        msg.prev_msg_id = self.msg_id
        msg.topic  = self.topic
        msg.sender = caller
        return msg

    def create_error_resp(self,error_msg:str):
        resp_msg = AgentMsg(AgentMsgType.TYPE_SYSTEM)
        resp_msg.create_time = time.time()

        resp_msg.rely_msg_id = self.msg_id
        resp_msg.body = error_msg
        resp_msg.topic  = self.topic
        resp_msg.sender = self.target
        resp_msg.target = self.sender

        return resp_msg

    def create_resp_msg(self,resp_body):
        resp_msg = AgentMsg()
        resp_msg.create_time = time.time()

        resp_msg.rely_msg_id = self.msg_id
        resp_msg.sender = self.target
        resp_msg.target = self.sender
        resp_msg.body = resp_body
        resp_msg.topic = self.topic

        return resp_msg

    def create_group_resp_msg(self,sender_id,resp_body):
        resp_msg = AgentMsg(AgentMsgType.TYPE_GROUPMSG)
        resp_msg.create_time = time.time()

        resp_msg.rely_msg_id = self.msg_id
        resp_msg.target = self.target
        resp_msg.sender = sender_id
        resp_msg.body = resp_body
        resp_msg.topic = self.topic

        return resp_msg

    def set(self,sender:str,target:str,body:str,topic:str=None,body_mime:str=None) -> None:
        self.sender = sender
        self.target = target
        self.body = body
        self.body_mime = body_mime
        self.create_time = time.time()
        if topic:
            self.topic = topic

    @staticmethod
    def create_image_body(images: [str], prompt: str = None):
        return json.dumps({"images": images, "prompt": prompt})

    @staticmethod
    def parse_image_body(image_body: str) -> Tuple[str, List[str]]:
        body = json.loads(image_body)
        return body.get("prompt"), body.get("images")

    @staticmethod
    def create_video_body(video: str, prompt: str = None):
        return json.dumps({"video": video, "prompt": prompt})

    @staticmethod
    def parse_video_body(video_body: str) -> Tuple[str, str]:
        body = json.loads(video_body)
        return body.get("prompt"), body.get("video")

    def set_image(self, sender: str, target: str, image_format: str, images: [str], prompt: str = None, topic: str = None):
        self.sender = sender
        self.target = target
        self.create_time = time.time()
        self.body_mime = f"image/{image_format}"
        self.body = self.create_image_body(images, prompt)
        if topic:
            self.topic = topic

    def is_image_msg(self) -> bool:
        if self.body_mime is None:
            return False
        if self.body_mime.startswith("image/"):
            return True
        return False

    def get_image_body(self) -> Tuple[str, List[str]]:
        if self.body_mime is None:
            return None
        if self.body_mime.startswith("image/"):
            return self.parse_image_body(self.body)
        return None

    def set_video(self, sender: str, target: str, video_format: str, video: str, prompt: str = None, topic: str = None):
        self.sender = sender
        self.target = target
        self.create_time = time.time()
        self.body_mime = f"video/{video_format}"
        self.body = self.create_video_body(video, prompt)
        if topic:
            self.topic = topic

    def get_video_body(self) -> Tuple[str, str]:
        if self.body_mime is None:
            return None
        if self.body_mime.startswith("video/"):
            return self.parse_video_body(self.body)
        return None

    def is_video_msg(self) -> bool:
        if self.body_mime is None:
            return False
        if self.body_mime.startswith("video/"):
            return True
        return False

    def is_audio_msg(self) -> bool:
        if self.body_mime is None:
            return False
        if self.body_mime.startswith("audio/"):
            return True
        return False

    def get_msg_id(self) -> str:
        return self.msg_id

    def get_sender(self) -> str:
        return self.sender

    def get_target(self) -> str:
        return self.target

    def get_prev_msg_id(self) -> str:
        return self.prev_msg_id

    def get_quote_msg_id(self) -> str:
        return self.quote_msg_id

    @classmethod
    def parse_function_call(cls,func_string:str):
        str_list = shlex.split(func_string)
        func_name = str_list[0]
        params = str_list[1:]
        return func_name, params
