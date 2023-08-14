
from .agent import ai_agent
from .templete import ai_agent_templete

class agent_manager:
    _instance = None

    def __init__(self) -> None:
        pass
   
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(agent_manager, cls).__new__(cls)
        return cls._instance
    

    def initial(self,root_dir:str) -> None:
        pass
    
  
    def get(self,agent_id) -> ai_agent:
        pass


    def get_templete(self,templete_id) -> ai_agent_templete:
        pass

    def install(self,templete_id) -> int:
        
        installer = None
        #installer.install(templete_id)
        pass

    def create(self,template,agent_name,agent_last_name,agent_introduce) -> ai_agent:
        pass


class agent_manager_client:
    def __init__(self) -> None:
        pass