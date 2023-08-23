
import logging
import toml

from aios_kernel import AIAgent,AIAgentTemplete
from package_manager import PackageEnv,PackageEnvManager,PackageMediaInfo,PackageInstallTask

logger = logging.getLogger(__name__)


class AgentManager:
    _instance = None

    def __init__(self) -> None:
        self.loaded_agent_instance = {}
        pass
   
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentManager, cls).__new__(cls)
        return cls._instance
    

    def initial(self,root_dir:str) -> None:
        self.agent_templete_env : PackageEnv = PackageEnvManager().get_env(f"{root_dir}templetes/agent_templetes.cfg")
        self.agent_env : PackageEnv = PackageEnvManager().get_env(f"{root_dir}agents/agents.cfg")
        if self.agent_templete_env is None:
            raise Exception("agent_manager initial failed")
        
    
    def get(self,agent_id:str) -> AIAgent:
        the_agent = self.loaded_agent_instance.get(agent_id)
        if the_agent:
            return the_agent
        
        # try load from disk
        agent_media_info = self.agent_env.load(agent_id)
        if agent_media_info is None:
            return None
        
        the_agent : AIAgent = self._load_agent_from_media(agent_media_info)
        if the_agent is None:
            logger.warn(f"load agent {agent_id} from media failed!")
            
        return the_agent


    def remove(self,agent_id:str)->int:
        pass

    def get_templete(self,templete_id) -> AIAgentTemplete:
        template_media_info = self.agent_templete_env.get(templete_id)
        if template_media_info is None:
            return None
        return self._load_templete_from_media(template_media_info)

    def install(self,templete_id) -> PackageInstallTask:
        installer = self.agent_templete_env.get_installer()
        return installer.install(templete_id)
    
    def uninstall(self,templete_id) -> int:
        pass 
    
    def _load_templete_from_media(self,templete_media:PackageMediaInfo) -> AIAgentTemplete:
        pass

    def _load_agent_from_media(self,agent_media:PackageMediaInfo) -> AIAgent:
        pass
    
    def create(self,template,agent_name,agent_last_name,agent_introduce) -> AIAgent:
        pass

