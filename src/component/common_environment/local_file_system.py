import json
import os
import aiofiles
from typing import Any,List,Dict
import chardet
from aios import SimpleAIAction
from aios import SimpleEnvironment

class FilesystemEnvironment(SimpleEnvironment):
    def __init__(self, workspace: str) -> None:
        super().__init__(workspace)
        self.root_path = workspace

        # if op["op"] == "create":
        #     await self.create(op["path"],op["content"])

        async def write(op):  
            is_append = op.get("is_append")
            if is_append is None:
                is_append = False
            return await self.write(op["path"],op["content"],is_append)
        self.add_ai_operation(SimpleAIAction(
            op="write",
            description="write file",
            func_handler=write,
        ))

        async def delete(op):  
            return await self.delete(op["path"])
        self.add_ai_operation(SimpleAIAction(
            op="delete",
            description="delete path",
            func_handler=delete,
        ))

        async def rename(op):  
            return await self.move(op["path"],op["new_name"])
        self.add_ai_operation(SimpleAIAction(
            op="rename",
            description="rename path",
            func_handler=rename,
        ))
    
    # file system operation: list,read,write,delete,move,stat
    # inner_function
    async def list(self,path:str,only_dir:bool=False) -> str:
        directory_path = self.root_path + path
        items = []

        with await aiofiles.os.scandir(directory_path) as entries:
            async for entry in entries:
                is_dir = entry.is_dir()
                if only_dir and not is_dir:
                    continue
                item_type = "directory" if is_dir else "file"
                items.append({"name": entry.name, "type": item_type})

        return json.dumps(items)
    
    # inner_function
    async def read(self,path:str) -> str:
        file_path = self.root_path + path
        cur_encode = "utf-8"
        async with aiofiles.open(file_path,'rb') as f:
            cur_encode = chardet.detect(await f.read())['encoding']

        async with aiofiles.open(file_path, mode='r', encoding=cur_encode) as f:
            content = await f.read(2048)
        return content
    

    # operation or inner_function (MOST IMPORTANT FUNCTION)
    async def write(self,path:str,content:str,is_append:bool=False) -> str:
        file_path = self.root_path + path
        try:
            if is_append:
                async with aiofiles.open(file_path, mode='a', encoding="utf-8") as f:
                    await f.write(content)
            else:
                if content is None:
                    # create dir
                    dir_path = self.root_path + path
                    os.makedirs(dir_path)
                    return True
                else:
                    file_path = self.root_path + path
                    os.makedirs(os.path.dirname(file_path),exist_ok=True)
                    async with aiofiles.open(file_path, mode='w', encoding="utf-8") as f:
                        await f.write(content)
                    return True
        
        except Exception as e:
            return str(e)
        return None
    
        
    # operation or inner_function
    async def delete(self,path:str) -> str:
        try:
            file_path = self.root_path + path
            os.remove(file_path)
        except Exception as e:
            return str(e)
        
        return None
    
    # operation or inner_function
    async def move(self,path:str,new_path:str) -> str:
        try:
            file_path = self.root_path + path
            new_path = self.root_path + new_path
            os.rename(file_path,new_path)
        except Exception as e:
            return str(e)
        
        return None
    
    # inner_function
    async def stat(self,path:str) -> str:
        try:
            file_path = self.root_path + path
            stat = os.stat(file_path)
            return json.dumps(stat)
        except Exception as e:
            return str(e)

    # operation or inner_function   
    async def symlink(self,path:str,target:str) -> str:
        try:
            #file_path = self.root_path + path
            target_path = self.root_path + target
            dir_path = os.path.dirname(target_path)
            os.makedirs(dir_path,exist_ok=True)
            os.symlink(path,target_path)
        except Exception as e:
            logger.error("symlink failed:%s",e)
            return str(e)
        
        return None