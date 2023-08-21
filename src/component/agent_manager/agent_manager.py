
import logging
import toml

from .agent import ai_agent
from .templete import ai_agent_templete
from package_manager import pkg_env,pkg_env_mgr,pkg_media_info,media_reader,pkg_install_task

logger = logging.getLogger(__name__)


class agent_manager:
    _instance = None

    def __init__(self) -> None:
        self.loaded_agent_instance = {}
        pass
   
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(agent_manager, cls).__new__(cls)
        return cls._instance
    

    def initial(self,root_dir:str) -> None:
        self.agent_templete_env : pkg_env = pkg_env_mgr().get_env(f"{root_dir}templetes/agent_templetes.cfg")
        self.agent_env : pkg_env = pkg_env_mgr().get_env(f"{root_dir}agents/agents.cfg")
        if self.agent_templete_env is None:
            raise Exception("agent_manager initial failed")
        
    
    def get(self,agent_id:str) -> ai_agent:
        the_agent = self.loaded_agent_instance.get(agent_id)
        if the_agent:
            return the_agent
        
        # try load from disk
        agent_media_info = self.agent_env.load(agent_id)
        if agent_media_info is None:
            return None
        
        the_agent = self._load_agent_from_media(agent_media_info)
        if the_agent is None:
            logger.warn(f"load agent {agent_id} from media failed!")
            
        return the_agent


    def remove(self,agent_id:str)->int:
        pass

    def get_templete(self,templete_id) -> ai_agent_templete:
        template_media_info = self.agent_templete_env.get(templete_id)
        if template_media_info is None:
            return None
        return self._load_templete_from_media(template_media_info)

    def install(self,templete_id) -> pkg_install_task:
        installer = self.agent_templete_env.get_installer()
        return installer.install(templete_id)
    
    def uninstall(self,templete_id) -> int:
        pass 
    
    def _load_templete_from_media(self,templete_media:pkg_media_info) -> ai_agent_templete:
        pass

    def _load_agent_from_media(self,agent_media:pkg_media_info) -> ai_agent:
        pass
    
    def create(self,template,agent_name,agent_last_name,agent_introduce) -> ai_agent:
        pass


class agent_manager_client:
    def __init__(self) -> None:
        pass