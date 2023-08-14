# installer download pkg by cid, than install it to target dir
import logging
import asyncio
import aiohttp
import aiofiles

from threading import RLock

from ndn_client import content_id
from .pkg import pkg_info
from .env import pkg_env

logger = logging.getLogger(__name__)

INSTALL_TASK_STATE_DONE = 0
INSTALL_TASK_STATE_CHECK_DEPENDENCY = 1
INSTALL_TASK_STATE_INSTALL_DEPENDENCY = 2
INSTALL_TASK_STATE_DOWNLOADING = 3
INSTALL_TASK_STATE_INSTALLING = 4
INSTALL_TAKS_STATE_ERROR = 5

class install_task:
    def __init__(self,owner:pkg_env) -> None:
        self.owner = owner
        self.state = INSTALL_TASK_STATE_CHECK_DEPENDENCY
        self.working_task = None
        self.error_str = None



class pkg_installer:
    def __init__(self,owner_env:pkg_env) -> None:
        self.all_tasks = {}
        self.owner_env = owner_env
    
    def install(self,pkg_name:str,
                install_from_dependency = False, can_upgrade = True,options = None)->Tuple[install_task,str]:
        media_info = self.owner_env.get_media_info(pkg_name)
        is_upgrade = False
        if media_info is not None:
            is_upgrade = True
            if can_upgrade is False:
                error_str = f"pkg:{pkg_name} already installed and can't upgrade"
                logger.error(error_str)
                return None,error_str
        
        pkg_id,version_str,content_id = pkg_info.parse_pkg_name(pkg_name)

        the_pkg_info = self.owner_env.lookup(pkg_id,version_str,content_id)
        if the_pkg_info is None:
            error_str = f"pkg:{pkg_name} ,content_id:{content_id} not found in index db"
            logger.error(error_str)
            return None,error_str
        
        result_task = self.all_tasks.get(the_pkg_info.cid)
        if result_task is not None:
            return result_task,None

        result_task = install_task()
        self.all_tasks[the_pkg_info.cid] = result_task
        async def install_pkg():
            # check dependency
            if await self.check_dependency(the_pkg_info) is False:
                error_str = f"pkg:{pkg_name} check dependency failed"
                logger.error(error_str)
                result_task.error_str = error_str
                result_task.state = INSTALL_TAKS_STATE_ERROR
                return
            
            # install dependency
            result_task.state = INSTALL_TASK_STATE_INSTALL_DEPENDENCY
            for depend_pkg_name in the_pkg_info.depends:
                # TODO：这里可能需要用安装队列，直接等待安装完成可能会太慢，也可能会导致循环等待
                sub_task,err_str = self.install(depend_pkg_name,True,can_upgrade,options)
                

        result_task.working_task = asyncio.create_task(install_pkg())
        return result_task,None

        
    def uninstall(self):
        pass

    async def check_dependency(self,pkg:pkg_info) -> bool:
        #TODO:这里可能会有循环依赖导致的递归无法退出的问题，需要记录已经检查过的pkg
        for depend_pkg_name in pkg.depends:
            depend_pkg_info = self.owner_env.lookup(depend_pkg_name)
            if depend_pkg_info is None:
                logger.warn(f"{pkg.name}'s depend pkg {depend_pkg_name} not found in index db")
                return False
            
            if await self.check_dependency(depend_pkg_info) is False:
                return False
    
        return True
        
        

        
        


