import environment
import agent_prompt,agent_msg

class ai_workflow:
    def __init__(self) -> None:
        self.rule_prompt : agent_prompt = None
        self.workflow_config = None
        self.context = None

    def load_from_disk(self,config_path:str,context_dir_path) -> int:
        pass

    def send_msg(self,msg:agent_msg,target_group:str = None) -> None:
        if target_group is None:
            target_group = self.get_default_group()   
        pass

    def run(self):

        pass

    def _pop_msg(self) -> Tuple[agent_msg,str]:
        pass

    def get_default_group(self) -> agent_group:
        pass

    def get_group(self,group_name:str) -> agent_group:
        pass

    def get_workflow_rule_prompt(self) -> agent_prompt:
        return self.rule_prompt

    def get_inner_environment(self) -> environment:
        pass

    def connect_to_environment(self,env:environment) -> None:
        pass