import asyncio,aiofiles,aiohttp
import logging
from typing import Optional

from .cid import ContentId 

logger = logging.getLogger(__name__)

NDN_GET_TASK_STATE_INIT = 0
NDN_GET_TAKS_CONNECTING = 1
NDN_GET_TASK_STATE_DOWNLOADING = 2
NDN_GET_TASK_STATE_VERIFYING = 3
NDN_GET_TASK_STATE_DONE = 4
NDN_GET_TASK_STATE_ERROR = 5

class NDN_GetTask:
    def __init__(self) -> None:
        self.cid:str = None
        self.target_path:str = None
        self.urls:[str] = None
        self.options:Optional[dict] = None

        self.working_task = None
        self.state = NDN_GET_TASK_STATE_INIT
        self.total_size = 0
        self.recv_bytes = 0
        self.write_bytes = 0
        self.error_str = None
        self.chunk_queue = None
       
        self.retry_count = 0
        self.used_urls = []
        self.hash_update = None
        
    
    def select_url(self,index:int)->str:
        return self.urls[0]
    
    def get_chunk_for_download(self)->bytes:
        pass

class NDN_Client:
    def __init__(self):
        self.cache_dir = ""
        self.default_ndn_http_gateway = ""
        self.all_task = {}
        self.memory_chunk_size = 1024*1024*2
        self.chunk_queue_size = 16

    def load_config(self,config:dict):
        if config.get("cache_dir"):
            self.cache_dir = config.get("cache_dir")
        if config.get("dndn_gateway"):
            self.default_ndn_http_gateway = config.get("ndn_gateway")

    def get_file(self,cid:ContentId,target_path:str,urls:{}=None,options:{}=None)->NDN_GetTask:
        get_task = self.all_task.get(cid.as_str())
        if get_task:
            return get_task
        else:
            get_task = NDN_GetTask()
            self.all_task[cid.as_str()] = get_task
            
            get_task.cid = cid
            get_task.target_path = target_path
            get_task.urls = urls
            get_task.options = options
            if get_task.urls is None:
                get_task.urls = [f"{self.default_ndn_http_gateway}/{cid.as_str()}"]
                logger.info(f"get_file {cid.as_str()} urls is None, use {get_task.urls[0]} as default")


            async def get_file_async():
                target_file = aiofiles.open(target, 'wb')
                # if file exist, check hash first

                http_session = aiohttp.ClientSession()
                resp = http_session.get(get_task.select_url(0))
                if resp.status != 200:
                    get_task.error_str = f"get_file {cid.as_str()} failed,http status:{resp.status}"
                    return
                get_task.total_size = resp.content_length
               
                async def write_file_async():
                    while True:
                        chunk = await get_task.chunk_queue.pop()
                        chunk_size = len(chunk)
                        if not chunk or chunk_size == 0:
                            break
                        get_task.hash_update.update(chunk)
                        await target_file.write(chunk)
                        get_task.write_bytes += chunk_size
                    
                    #verify
                    get_task.state = NDN_GET_TASK_STATE_VERIFYING
                    await target_file.close()
                    return

                write_task = asyncio.create_task(write_file_async())
                while True:
                    await get_task.chunk_queue.pop()
                    chunk = resp.content.read(self.memory_chunk_size) 
                    chunk_size = len(chunk)
                    if not chunk or chunk_size == 0:
                        break

                    get_task.recv_bytes += len(chunk)
                    get_task.chunk_queue.push(chunk)

                
                get_task.state = NDN_GET_TASK_STATE_DONE
                await write_task

            get_task.working_task = asyncio.create_task(get_file_async())
            return get_task

    