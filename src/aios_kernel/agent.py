from typing import Optional
import logging
import llm_kernel,llm_work_task

logger = logging.getLogger(__name__)



class agent_msg:
    def __init__(self) -> None:
        pass

class agent_prompt:
    def __init__(self) -> None:
        pass

    def as_str()->str:
        pass

class agent_chat_session:
    def __init__(self) -> None:
        self.llm_model_name = None
        self.llm_instance = None
        self.max_token_size = 0
        self.chat_msg_list = None
        self.enable_function = True

        pass

    def chat(self,message:str) -> None:
        pass
    # Key functions, let the AI Agent try to run.
    def completion(self)->llm_work_task:
        if self.llm_instance is None:
            self.llm_instance = llm_kernel.craete(self.llm_model_name)
            if self.llm_instance is None:
                logger.fatal(f"cann't get llm_kerenel : {self.llm_model_name}")
                return 
        
        llm_work_task = self.llm_instance.completion(self._get_prompt(),self.max_token_size)
        return llm_work_task

    def _get_prompt(str) -> str:
        pass    

class ai_agent:
    def __init__(self) -> None:
        pass    

    def get_chat_session(self,chat_user_name:str,session_id:Optional[str]) -> agent_chat_session:
        pass



    #chat_session = agent.get_default_chat_session("master");
    #chat_session.chat("给我讲一个英文笑话!");
    #chat_session.completion();
    #print(chat_session.last_msg());