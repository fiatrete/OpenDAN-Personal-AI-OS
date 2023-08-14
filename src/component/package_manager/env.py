
import logging
import toml

from .pkg import pkg_info,pkg_media_info 
from .installer import pkg_installer

logger = logging.getLogger(__name__)

#pkg_env_mgr,以cfg_path为key管理多个pkg_env,是个单件
class pkg_env_mgr:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(pkg_env_mgr, cls).__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        self._pkg_envs = {}
        pass

    def get_env(self,cfg_path:str) -> pkg_env:
        if cfg_path in self._pkg_envs:
            return self._pkg_envs[cfg_path]
        else:
            pkg_env = pkg_env(cfg_path)
            self._pkg_envs[cfg_path] = pkg_env
            return pkg_env

    def get_user_env(self) -> pkg_env:
        pass

    def get_system_env(self) -> pkg_env:
        pass

class pkg_env:
    def __init__(self,cfg_path:str,inheritance = True) -> None:
        self.prefixs : list[str]= []
        self.is_strict : bool = True
        self.parent_envs : list[pkg_env] = [pkg_env_mgr().get_user_env()]
        self.index_dbs = None

        self.cfg_path = cfg_path
        self._load_pkg_cfg(cfg_path)
        pass

    def load(self,pkg_name:str,cid:None) -> pkg_media_info:
        if cid is None:
            #lookup pkg's cid from indexDb
            pkg_id,verion_str,cid = pkg_info.parse_pkg_name(pkg_name)
            if cid is None:
                #lookup include pkg-index-db search
                pkg_info = self.lookup(pkg_id,verion_str)
                if pkg_info is not None:
                    return self.load(pkg_id,pkg_info.cid)
                
                if self.is_strict is False:
                    #load pkg not in index-db, easy for debug
                    for prefix in self.prefixs:
                        fullpath = prefix + pkg_name
                        logger.debug("try load {pkg_name} at {fullpath} ...")
                        if pkg_env.is_valied_media(fullpath):
                            return self.load_pkg_media_info(fullpath)
                        
                logger.warn(f"load {pkg_name} failed: pkg not found in index-db and pkg_dirs")
                return None
            else:
                #got cid here~
                return self.load(pkg_id,cid)
        else:
            #search pkg_id#cid and load pkg_media_info
            for prefix in self.prefixs:
                fullpath =f"{prefix}{pkg_id}#{cid}"
                logger.debug(f"try load {pkg_name} from {fullpath}")
                if pkg_env.is_valied_media(fullpath):
                    media_info = self.load_pkg_media_info(fullpath)
                    return media_info
            
            logger.warn(f"load {pkg_id}#{cid} error,not found")
    

    def get_pkg_media_info(self,pkg_name:str)->pkg_media_info:
        pass

    def load_pkg_media_info(self,pkg_full_path:str) -> pkg_media_info:
        pass
    

    def lookup(self,pkg_id:str,version_str:str) -> pkg_info:
        
        pass

    def get_installer(self) -> pkg_installer:
        pass

    @classmethod    
    def is_valied_media(pkg_full_path:str) -> bool:
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