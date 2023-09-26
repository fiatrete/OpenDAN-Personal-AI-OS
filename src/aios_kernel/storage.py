from typing import Any
from pathlib import Path
import os
import logging
import toml
import aiofiles

logger = logging.getLogger(__name__)

_file_dir = os.path.dirname(__file__)

class ResourceLocation:
    def __init__(self) -> None:
        pass

class FeatureItem:
    def __init__(self) -> None:
        pass

class UserConfigItem:
    def __init__(self,desc:str=None) -> None:
        self.default_value = None 
        self.is_optional = False
        self.item_type = "str"
        self.desc = desc
        self.value = None
        self.user_set = False

    def clone(self):
        new_config_item = UserConfigItem()
        new_config_item.default_value = self.default_value
        new_config_item.is_optional = self.is_optional
        new_config_item.desc = self.desc
        new_config_item.item_type = self.item_type
        new_config_item.value = self.value
        return new_config_item

class UserConfig:
    def __init__(self) -> None:
        self.config_table = {}
        self.user_config_path:str = None


    def add_user_config(self,key:str,desc:str,is_optional:bool,default_value:Any=None,item_type="str") -> None:
        if self.config_table.get(key) is not None:
            logger.warning("user config key %s already exist, will be overrided",key)
    
        new_config_item = UserConfigItem()
        new_config_item.default_value = default_value
        new_config_item.is_optional = is_optional
        new_config_item.desc = desc
        new_config_item.item_type = item_type
        self.config_table[key] = new_config_item
        
    async def load_value_from_file(self,file_path:str,is_user_config = False) -> None:
        try: 
            all_config = toml.load(file_path)
            if all_config is not None:
                for key,value in all_config.items():
                    config_item = self.config_table.get(key)
                    if config_item is None:
                        logger.warning("user config key %s not exist",key)
                        continue
                    config_item.value = value
                    config_item.user_set = is_user_config

        except Exception as e:
            logger.warn(f"load user config from {file_path} failed!")


    async def save_to_user_config(self) -> None:
        will_save_config = {}
        for key,value in self.config_table.items():
            if value.user_set:
                will_save_config[key] = value.value
        
        if len(will_save_config) > 0:
            try:
                directory = os.path.dirname(self.user_config_path)
                if not os.path.exists(directory):
                    os.makedirs(directory)

                async with aiofiles.open(self.user_config_path,"w") as f:
                    toml_str = toml.dumps(will_save_config)
                    await f.write(toml_str)
            except Exception as e:
                logger.error(f"save user config to {self.user_config_path} failed!")
                return False
        
        return True

    def get_config_item(self,key:str) -> Any:
        config_item = self.config_table.get(key)
        if config_item is None:
            raise Exception("user config key %s not exist",key)

        return config_item
    
    def get_value(self,key:str)->Any:
        config_item = self.config_table.get(key)
        if config_item is None:
            raise Exception("user config key %s not exist",key)
        
        if config_item.value is None:
            return config_item.default_value

        return config_item.value

    def set_value(self,key:str,value:Any) -> None:
        config_item = self.config_table.get(key)
        if config_item is None:
            logger.warning("user config key %s not exist",key)
            return 
        
        config_item.value = value
        config_item.user_set = True
        #TODO: save to file?

        
    def check_config(self) -> None:
        check_result = {}
        for key,config_item in self.config_table.items():
            if config_item.value is None and not config_item.is_optional:
                check_result[key] = config_item
        
        if len(check_result) > 0:
            return check_result
        else:
            return None

# storage sytem for current user
class AIStorage:
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = AIStorage()
        return cls._instance

    def __init__(self) -> None:
        self.is_dev_mode = False
        self.user_config = UserConfig()

    async def initial(self)->bool:
        self.user_config.user_config_path = str(self.get_myai_dir() / "etc/system.cfg.toml")
        await self.user_config.load_value_from_file(self.get_system_dir() + "/system.cfg.toml")
        await self.user_config.load_value_from_file(self.user_config.user_config_path,True)

    async def enable_feature(self,feature_name:str) -> None:
        pass

    async def disable_feature(self,feature_name:str) -> None:
        pass
    
    async def set_feature_init_result(self,feature_name:str,result:bool) -> None:
        pass

    async def is_feature_enable(self,feature_name:str) -> bool:
        pass

    def get_user_config(self) -> UserConfig:
        return self.user_config

    def get_system_dir(self) -> str:
        """ 
        system dir is dir for aios system
        /opt/aios
        """
        if self.is_dev_mode:
            return os.path.abspath(_file_dir + "/../")
        else:
            return "/opt/aios/"
        
    
    def get_system_app_dir(self)->str:
        """
        system app dir is the dir for aios build-in app 
        /opt/aios/app
        """
        if self.is_dev_mode:
            return os.path.abspath(_file_dir + "/../../rootfs/")
        else:
            return "/opt/aios/app/"
    
    def get_myai_dir(self) -> str:
        """
        my ai dir is the dir for user to store their ai app and data
        ~/myai/
        """
        return Path.home() / "myai"
        
    def get_db(self,app_name:str)->ResourceLocation:
        pass

    def open_file(self,file_path:str,options:dict):
        pass

    def get_named_object(self,name:str) -> Any:
        pass

    def put_named_object(self,name:str,obj:Any) -> None:
        pass
    
    async def try_create_file_with_default_value(self,path:str,default_value:str):
        if os.path.exists(path):
            return None
        
        try:
            directory = os.path.dirname(path)
            if not os.path.exists(directory):
                os.makedirs(directory)
            async with aiofiles.open(path,"w") as f:
                await f.write(default_value)

        except Exception as e:
            logger.error(f"open or create file {path} failed! {str(e)}")


