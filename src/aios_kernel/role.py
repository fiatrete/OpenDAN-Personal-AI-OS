from .agent import AIAgent

class AIRole:
    def __init__(self) -> None:
        self.agent_instance_id : str = None
        self.role_name : str = None
        self.agent : AIAgent = None
        self.introduce : str = None

    def load_from_config(self,config:dict) -> bool:
        pass

    def get_intro(self) -> str:
        return self.introduce

    def get_name(self) -> str:
        return self.role_name
    
class AIRoleGroup:
    def __init__(self) -> None:
        self.roles : dict[str,str]= None
        pass


    