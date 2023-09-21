
import logging
import toml
import os

from .pkg import PackageInfo,PackageMediaInfo
from .media_reader import MediaReader

logger = logging.getLogger(__name__)


class PackageEnv:
    def __init__(self,cfg_path:str) -> None:
        self.pkg_dir : str = "./pkgs/"
        self.pkg_obj_dir : str = "./.pkgs/"

        self.locked_index : str = "./pkg.lock"
        self.is_strict : bool = True
        self.parent_envs : list[PackageEnv] = []
        self.index_dbs = None

        self.env_dir = None
        self.cfg_path = cfg_path
        self._load_pkg_cfg(cfg_path)
        pass

    def load_from_config(self,config:dict) -> bool:
        if config.get("main") is not None:
            self.pkg_dir = os.path.abspath(self.env_dir + "/" + config["main"])

        if config.get("cache") is not None:
            self.pkg_obj_dir = os.path.abspath(self.env_dir + "/ " + config["cache"])

    def load(self,pkg_name:str,search_parent=True) -> PackageMediaInfo:
        pkg_path = None
        pkg_id,verion_str,cid = PackageInfo.parse_pkg_name(pkg_name)
        
        if cid is None:
            if verion_str is None:
                pkg_path = f"{self.pkg_dir}/{pkg_id}"
            else:
                #TODO fix bug about channel here
                channel:str = self.get_pkg_channel_from_version(verion_str)
                the_version:str = self.get_exact_version_from_installed(verion_str)
                if the_version is None:
                    logger.warn(f"load {pkg_name} failed: no match version from {verion_str}")
                    return None
                if channel is None:
                    pkg_path = f"{self.pkg_dir}/{pkg_id}#{the_version}"
                else:
                    pkg_path = f"{self.pkg_dir}/{pkg_id}#{channel}#{the_version}"
        else:
            pkg_path = f"{self.pkg_obj_dir}/.{pkg_id}/{cid}"

        media_info:PackageMediaInfo = self.try_load_pkg_media_info(pkg_path)
        if media_info is None:
            if search_parent is True and self.parent_envs is not None:
                for parent_env in self.parent_envs:
                    media_info = parent_env.load(pkg_id,False)
                    if media_info is not None:
                        return media_info
            
        if media_info is None:
            logger.warn(f"pkg_load {pkg_id}, cid:{cid} error,not found ,search_parent={search_parent}")

        return media_info
    
    def get_exact_version_from_installed(self,verion_str:str) -> str:
        pass

    def get_pkg_channel_from_version(self,pkg_version:str) -> str:
        args = pkg_version.split("~")
        if len(args) == 1:
            return None
        else: 
            return args[0]
        

    def get_pkg_media_info(self,pkg_name:str)->PackageMediaInfo:
        pass

    def try_load_pkg_media_info(self,pkg_full_path:str) -> PackageMediaInfo:
        the_result : PackageMediaInfo = None
        logger.debug(f"try load pkng from:{pkg_full_path}")
        if os.path.isdir(pkg_full_path):
            the_result = PackageMediaInfo(pkg_full_path,"dir")
        
        return the_result
    
    def _create_media_loader(self,media_info:PackageMediaInfo) -> MediaReader:
        match media_info.media_type:
            case "dir":
                from .media_reader import FolderMediaReader 
                return FolderMediaReader(media_info.full_path)
                
        logger.error(f"create media loader for {media_info} failed!")
        return None  

    def get_installed_pkg_info(self,pkg_name:str) -> PackageInfo:
        pass

    def lookup(self,pkg_id:str,version_str:str) -> PackageInfo:
        # to make sure pkg.cid is correct, we MUST verfiy eveything here 
        pass

    @classmethod    
    def is_valied_media(pkg_full_path:str) -> bool:
        pass
    
    def do_pkg_media_trans(self,pkg_info:PackageInfo,source_path:str,target_path:str) -> bool:
        pass

    def _load_pkg_cfg(self,cfg_path:str):
        if cfg_path is None:
            return
        
        cfg = None
        if len(cfg_path) < 1:
            return
        try:
            cfg = toml.load(cfg_path)
            self.env_dir = os.path.abspath(os.path.dirname(cfg_path))
            self.cfg_path = os.path.abspath(cfg_path)
        except Exception as e:
            logger.error(f"read pkg cfg from {cfg_path} failed! unexpected error occurred: {str(e)}")
            return

        return self.load_from_config(cfg)

    
   
    def _preprocess_prefixs(self,prefixs):
        pass

class PackageEnvManager:
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = PackageEnvManager()
        return cls._instance
    
    def __init__(self) -> None:
        self._pkg_envs = {}
        
    def get_env(self,cfg_path:str) -> PackageEnv:
        if cfg_path in self._pkg_envs:
            return self._pkg_envs[cfg_path]
        else:
            pkg_env = PackageEnv(cfg_path)
            self._pkg_envs[cfg_path] = pkg_env
            return pkg_env

    def get_user_env(self) -> PackageEnv:
        pass

    def get_system_env(self) -> PackageEnv:
        pass
