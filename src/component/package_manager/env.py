
import logging
import toml

from .pkg import PackageInfo,PackageMediaInfo 
from .installer import PackageInstaller

logger = logging.getLogger(__name__)

class PackageEnvManager:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PackageEnvManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        self._pkg_envs = {}
       
        pass

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

class PackageEnv:
    def __init__(self,cfg_path:str) -> None:
        self.pkg_dir : str = ""
        self.pkg_obj_dir : str = ""
        self.is_strict : bool = True
        self.parent_envs : list[PackageEnv] = None
        self.index_dbs = None
        
        self.cfg_path = cfg_path
        self._load_pkg_cfg(cfg_path)
        pass

    def load(self,pkg_name:str,search_parent=True) -> PackageMediaInfo:
        pkg_path = None
        pkg_id,verion_str,cid = PackageInfo.parse_pkg_name(pkg_name)
        
        if cid is None:
            if verion_str is None:
                channel:str = self.get_pkg_channel_from_version(verion_str)
                if channel is None:
                    pkg_path = f"{self.pkg_dir}{pkg_id}"
                else: 
                    pkg_path = f"{self.pkg_dir}{pkg_id}#{channel}" 
            else:
                channel:str = self.get_pkg_channel_from_version(verion_str)
                the_version:str = self.get_exact_version_from_installed(verion_str)
                if the_version is None:
                    logger.warn(f"load {pkg_name} failed: no match version from {verion_str}")
                    return None
                if channel is None:
                    pkg_path = f"{self.pkg_dir}{pkg_id}#{the_version}"
                else:
                    pkg_path = f"{self.pkg_dir}{pkg_id}#{channel}#{the_version}"
        else:
            pkg_path = f"{self.pkg_obj_dir}.{pkg_id}/{cid}"

        media_info:PackageMediaInfo = self.try_load_pkg_media_info(pkg_path)
        if media_info is None:
            if search_parent:
                for parent_env in self.parent_envs:
                    media_info = parent_env.load(pkg_id,cid,False)
                    if media_info is not None:
                        return media_info
                    
        logger.warn(f"load {pkg_id}#{cid} error,not found ,search_parent={search_parent}")
        return None
    
    def get_exact_version_from_installed(self,verion_str:str) -> str:
        pass

    def get_pkg_channel_from_version(self,pkg_version:str) -> str:
        pass

    def get_pkg_media_info(self,pkg_name:str)->PackageMediaInfo:
        pass

    def try_load_pkg_media_info(self,pkg_full_path:str) -> PackageMediaInfo:
        pass
    

    def get_installed_pkg_info(self,pkg_name:str) -> PackageInfo:
        pass

    def lookup(self,pkg_id:str,version_str:str) -> PackageInfo:
        # to make sure pkg.cid is correct, we MUST verfiy eveything here 
        pass

    def get_installer(self) -> PackageInstaller:
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
        except Exception as e:
            logger.error(f"read pkg cfg from {cfg_path} failed! unexpected error occurred: {str(e)}")
            return
        
        if cfg:
            if cfg.env:
                if cfg.env.is_strict is not None:
                    self.is_strict = cfg.env.is_strict
                
                if cfg.env.prefixs is not None:
                    self.prefixs = self._preprocess_prefixs(cfg.env.prefixs)
    
   
    def _preprocess_prefixs(self,prefixs):
        pass