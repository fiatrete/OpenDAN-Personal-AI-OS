from typing import Optional

import logging

logger = logging.getLogger(__name__)

class AgentMsg:
    def __init__(self) -> None:
        self.sender = None
        self.target = None
        self.body = None

    def get_msg_id(self) -> str:
        pass

    def get_sender(self) -> str:
        return self.sender

    def get_target(self) -> str:
        return self.target

    # return workflow_name, role_name, session_id
    def parser_target(self,target:str) -> None:
        pass

class AgentPrompt:
    def __init__(self) -> None:
        pass

    def as_str(self)->str:
        pass

    def append(self,prompt) -> None:
        pass

# chat session store the chat history between owner and agent
# chat session might be large, so can read / write at stream mode.
class AIChatSession:
    def __init__(self) -> None:
        pass

    def get_owner_id(self) -> str:
        pass

    def append_post(self,msg:AgentMsg) -> None:
        """append msg to session, msg is post from session (owner => msg.target)"""
        pass

    def append_recv(self,msg:AgentMsg) -> None:
        """append msg to session, msg is recv from msg'sender (msg.sender => owner)"""
        pass    

    def attach_event_handler(self,handler) -> None:
        """chat session changed event handler"""
        pass

    #TODO : add iterator interface for read chat history 

class AIAgentTemplete:
    def __init__(self) -> None:
        pass
    
class AIAgent:
    def __init__(self) -> None:
        self.chat_sessions = None    
        self.llm_model_name = None
        self.max_token_size = 0
        self.instance_id = None
        self.template_id = None

    def get_id(self) -> str:
        return self.instance_id

    def get_template_id(self) -> str:
        return self.template_id

    def get_chat_session_for_msg(self,msg:AgentMsg) -> AIChatSession:
        pass

    def get_chat_session(self,sender:str,session_id:str) -> AIChatSession:
        pass

    def get_llm_model_name(self) -> str:
        return self.llm_model_name
    
    def get_max_token_size(self) -> int:
        return self.max_token_size

