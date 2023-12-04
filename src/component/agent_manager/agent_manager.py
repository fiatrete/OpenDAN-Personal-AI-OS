import importlib
import logging
import toml
import os
import sys
import runpy
from typing import Any, Callable, Dict, List, Optional, Union

from aios import AIAgent,AIAgentTemplete,AIStorage,Environment,BaseAIAgent,PackageEnv,PackageEnvManager,PackageMediaInfo,PackageInstallTask

logger = logging.getLogger(__name__)

default_agent_cfg = """
main = "./"
cache = "./.agents"
"""

class AgentManager:
    _instance = None

    @classmethod
    def get_instance(cls)->'AgentManager':
        if cls._instance is None:
            cls._instance = AgentManager()
        return cls._instance

    def __init__(self) -> None:
        self.agent_templete_env : PackageEnv = None
        self.agent_env : PackageEnv = None
        self.db_path : str = None
        self.loaded_agent_instance : Dict[str,BaseAIAgent] = None

    async def initial(self) -> None:
        system_app_dir = AIStorage.get_instance().get_system_app_dir()
        user_data_dir = AIStorage.get_instance().get_myai_dir()

        self.agent_templete_env : PackageEnv = PackageEnvManager().get_env(f"{system_app_dir}/templates/templetes.cfg")
        sys_agent_env : PackageEnv = PackageEnvManager().get_env(f"{system_app_dir}/agents/agents.cfg")
        user_agent_config_path = f"{user_data_dir}/agents/agents.cfg"
        await AIStorage.get_instance().try_create_file_with_default_value(user_agent_config_path,default_agent_cfg)
        self.agent_env : PackageEnv = PackageEnvManager().get_env(user_agent_config_path)
        self.agent_env.parent_envs.append(sys_agent_env)

        self.db_path = f"{user_data_dir}/messages.db"
        self.loaded_agent_instance = {}

        return True

    async def scan_all_agent(self)->None:
        pass


    async def is_exist(self,agent_id:str) -> bool:
        the_aget = await self.get(agent_id)
        if the_aget:
            return True
        return False

    async def get(self,agent_id:str) -> AIAgent:
        the_agent = self.loaded_agent_instance.get(agent_id)
        if the_agent:
            return the_agent

        # try load from disk
        agent_media_info = self.agent_env.load(agent_id)
        if agent_media_info is None:
            return None

        the_agent : AIAgent = await self._load_agent_from_media(agent_media_info)
        if the_agent is None:
            logger.warn(f"load agent {agent_id} from media failed!")
            return None

        the_agent.chat_db = self.db_path
        return the_agent

    def remove(self,agent_id:str)->int:
        pass

    async def get_templete(self,templete_id) -> AIAgentTemplete:
        template_media_info = self.agent_templete_env.get(templete_id)
        if template_media_info is None:
            return None
        return self._load_templete_from_media(template_media_info)

    def install(self,templete_id) -> PackageInstallTask:
        installer = self.agent_templete_env.get_installer()
        return installer.install(templete_id)

    def uninstall(self,templete_id) -> int:
        pass

    async def _load_templete_from_media(self,templete_media:PackageMediaInfo) -> AIAgentTemplete:
        pass

    async def _load_agent_from_media(self,agent_media:PackageMediaInfo) -> BaseAIAgent:
        reader = self.agent_env._create_media_loader(agent_media)
        if reader is None:
            logger.error(f"create media loader for {agent_media} failed!")
            return None

        try:
            config_file = await reader.read("agent.toml","r")
            if config_file is None:
                logger.error(f"read agent config from {agent_media} failed!")
                return None

            config_data = await config_file.read()
            config = toml.loads(config_data)
            result_agent = AIAgent()

            if "owner_env" in config:
                owner_env = config["owner_env"]
                _, ext = os.path.splitext(owner_env)
                if ext == ".py":
                    env_path = os.path.join(agent_media.full_path, owner_env)
                    owner_env = runpy.run_path(env_path)["init"]()
                    config["owner_env"] = owner_env
                else:
                    owner_env = Environment.get_env_by_id(config["owner_env"])
                config["owner_env"] = owner_env

            if result_agent.load_from_config(config) is False:
                logger.error(f"load agent from {agent_media} failed!")
                return None
            return result_agent
        except Exception as e:
            custom_agent = os.path.join(agent_media.full_path,"agent.py")
            if not os.path.exists(custom_agent):
                logger.error(f"read agent.toml cfg from {agent_media} failed! unexpected error occurred: {str(e)}")
                return None

            agent = runpy.run_path(custom_agent)
            if "init" not in agent:
                logger.error(f"read agent.toml cfg from {agent_media} failed! unexpected error occurred: {str(e)}")
                return None
            return agent["init"]()



    def create(self,template,agent_name,agent_last_name,agent_introduce) -> AIAgent:
        pass

