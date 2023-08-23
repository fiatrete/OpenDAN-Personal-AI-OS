import asyncio
import aiohttp
import aiofiles
STATE_DONE = 0
STATE_DOWNLOADING = 1
class install_task:
    def __init__(self) -> None:
        self.download_task = None
        self.state = STATE_DOWNLOADING
        self.recv_bytes = 0
        self.total_bytes = 0 

class install_task_mgr:
    def __init__(self) -> None:
        self.all_tasks = {}
        
    def create_install_task(self,url:str,target:str):
        owner = self 
        this_task = self.all_tasks.get(url)
        if this_task is not None:
            return this_task
    
        this_task = install_task()
        self.all_tasks[url] = this_task
        async def down_and_write():
            async with aiofiles.open(target, 'wb') as file:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        while True:
                            chunk = await response.content.read(1024*1024*16) 
                            this_task.recv_bytes += len(chunk)
                            if not chunk:
                                break
                            await file.write(chunk)
                        print(f"download task {url} done!")    
                        this_task.state = STATE_DONE           
                        del owner.all_tasks[url]  
                        
        this_task.download_task = asyncio.create_task(down_and_write())
        return this_task
            


async def test_wait_download(mgr):
    this_task = mgr.create_install_task("https://www.cyfs.com/download/beta/cyberchat/android/latest","test.pkg")
    await this_task.download_task

def test_timer_download(mgr):
    this_task = mgr.create_install_task("https://www.cyfs.com/download/beta/cyberchat/android/latest","test.pkg")
    # start timer
    async def check_timer():
        while this_task.state == STATE_DOWNLOADING:
            await r = asyncio.sleep(1)
            print(f"download bytes:{this_task.recv_bytes}")
        print("download complete!")
    
    asyncio.create_task(check_timer())

async def test_main():
    mgr = install_task_mgr()
    test_timer_download(mgr)
    await test_wait_download(mgr)
    await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(test_main())