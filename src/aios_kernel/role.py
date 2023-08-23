from .agent import ai_agent

class ai_role:
    def __init__(self) -> None:
        self.agent_instance_id : str = None
        self.role_name : str = None
        self.agent : ai_agent = None
        self.introduce : str = None

    def load_from_config(self,config:dict) -> bool:
        pass
    
    def get_intro(self) -> str:
        return self.introduce

    def get_name(self) -> str:
        return self.role_name
    
class ai_role_group:
    def __init__(self) -> None:
        self.roles : dict[str,str]= None
        pass


    