# this env is designed for workflow owner filesystem, support file/directory operations

import json
import logging
import os
import aiofiles
from typing import Any,List
import chardet
from ..agent.agent_base import AgentMsg,AgentTodo,AgentPrompt,AgentTodoResult
from ..agent.ai_function import AIFunction,SimpleAIFunction, SimpleAIOperation
from ..storage.storage import AIStorage,ResourceLocation
from .environment import SimpleEnvironment, CompositeEnvironment



logger = logging.getLogger(__name__)

class TodoListType:
    TO_WORK = "work"
    TO_LEARN = "learn"

class TodoListEnvironment(SimpleEnvironment):
    def __init__(self, root_path, list_type) -> None:
        super.__init__(list_type)
        self.root_path = os.path.join(root_path, list_type)
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)
        self.known_todo = {}

        async def create_todo(params):  
            todoObj = AgentTodo.from_dict(params["todo"])
            parent_id = params.get("parent")
            return await self.create_todo(parent_id,todoObj)
        self.add_ai_operation(SimpleAIOperation(
            op="create_todo",
            description="create todo",
            func_handler=create_todo,
        ))


        async def update_todo(params):
            todo_id = params["id"]
            new_stat = params["state"]
            return await self.update_todo(todo_id,new_stat)
        self.add_ai_operation(SimpleAIOperation(
            op="update_todo",
            description="update todo",
            func_handler=update_todo,
        ))

 
    # Task/todo system , create,update,delete,query
    async def get_todo_tree(self,path:str = None,deep:int = 4):
        if path:
            directory_path = os.path.join(self.root_path, path)
        else:
            directory_path = self.root_path

        
        str_result:str = "/todos\n"
        todo_count:int = 0 

        async def scan_dir(directory_path:str,deep:int):
            nonlocal str_result
            nonlocal todo_count
            if deep <= 0:
                return
            
            if os.path.exists(directory_path) is False:
                return 
            
            for entry in os.scandir(directory_path):
                is_dir = entry.is_dir()
                if not is_dir:
                    continue

                if entry.name.startswith("."):
                    continue
                
                todo_count = todo_count +  1
                str_result = str_result + f"{'  '*(4-deep)}{entry.name}\n"
                await scan_dir(entry.path,deep-1)

        await scan_dir(directory_path,deep)
        return str_result,todo_count

    async def get_todo_list(self,agent_id:str,path:str = None)->List[AgentTodo]:
        logger.info("get_todo_list:%s,%s",agent_id,path)
        if path:
            directory_path = os.path.join(self.root_path, path)
        else:
            directory_path = self.root_path

        result_list:List[AgentTodo] = []

        async def scan_dir(directory_path:str,deep:int,parent:AgentTodo=None):
            nonlocal result_list
            if os.path.exists(directory_path) is False:
                return 

            for entry in os.scandir(directory_path):
                is_dir = entry.is_dir()
                if not is_dir:
                    continue

                if entry.name.startswith("."):
                    continue
                
                todo = await self.get_todo_by_fullpath(entry.path)
                if todo:
                    if todo.worker:
                        if todo.worker != agent_id:
                            continue
                        
                    if parent:
                        parent.sub_todos[todo.todo_id] = todo
                    
                    result_list.append(todo)
                    todo.rank = int(todo.create_time)>>deep
                    await scan_dir(entry.path,deep + 1,todo)
            
            return 

        await scan_dir(directory_path,0) 
        #sort by rank
        result_list.sort(key=lambda x:(x.rank,x.title))
        logger.info("get_todo_list return,todolist.length() is %d",len(result_list))
        return result_list

    async def get_todo_by_fullpath(self,path:str) -> AgentTodo:
        logger.info("get_todo_by_fullpath:%s",path)

        detail_path = path + "/detail"
        try:
            async with aiofiles.open(detail_path, mode='r', encoding="utf-8") as f:
                content = await f.read(4096)
                logger.debug("get_todo_by_fullpath:%s,content:%s",path,content)
                todo_dict = json.loads(content)
                result_todo =  AgentTodo.from_dict(todo_dict)
                if result_todo:
                    relative_path = os.path.relpath(path, self.root_path)
                    if not relative_path.startswith('/'):
                        relative_path = '/' + relative_path
                    result_todo.todo_path = relative_path
                    self.known_todo[result_todo.todo_id] = result_todo
                else:
                    logger.error("get_todo_by_path:%s,parse failed!",path)
                
                return result_todo
        except Exception as e:
            logger.error("get_todo_by_path:%s,failed:%s",path,e)
            return None
        
    async def get_todo(self,id:str) -> AgentTodo:
        return self.known_todo.get(id)

    async def create_todo(self,parent_id:str,todo:AgentTodo) -> str:
        try:
            if parent_id:
                if parent_id not in self.known_todo:
                    logger.error("create_todo failed: parent_id not found!")
                    return False
                
                parent_path = self.known_todo.get(parent_id).todo_path
                todo_path = f"{parent_path}/{todo.title}"
            else:
                todo_path = todo.title

            dir_path = f"{self.root_path}/{todo_path}"
    
            os.makedirs(dir_path)
            detail_path = f"{dir_path}/detail"
            if todo.todo_path is None:
                todo.todo_path = todo_path
            logger.info("create_todo %s",detail_path)
            async with aiofiles.open(detail_path, mode='w', encoding="utf-8") as f:
                await f.write(json.dumps(todo.to_dict()))
                self.known_todo[todo.todo_id] = todo
        except Exception as e:
            logger.error("create_todo failed:%s",e)
            return str(e)
        
        return None

    async def update_todo(self,todo_id:str,new_stat:str)->str:
        try:
            todo : AgentTodo = self.known_todo.get(todo_id)
            if todo:
                todo.state = new_stat
                detail_path =  f"{self.root_path}/{todo.todo_path}/detail"
                async with aiofiles.open(detail_path, mode='w', encoding="utf-8") as f:
                    await f.write(json.dumps(todo.to_dict()))
                    return None
            else:
                return "todo not found."
        except Exception as e:
            return str(e)
    
    async def append_worklog(self, todo:AgentTodo, result:AgentTodoResult):
        worklog = f"{self.root_path}/{todo.todo_path}/.worklog"

        async with aiofiles.open(worklog, mode='w+', encoding="utf-8") as f:
            content = await f.read()
            if len(content) > 0:
                json_obj = json.loads(content)
            else:
                json_obj = {}
            logs = json_obj.get("logs")
            if logs is None:
                logs = []
            logs.append(result.to_dict())
            json_obj["logs"] = logs
            await f.write(json.dumps(json_obj))

class FilesystemEnvironment(SimpleEnvironment):
    def __init__(self, root_path: str, env_id: str) -> None:
        super().__init__(env_id)
        self.root_path = root_path


        # if op["op"] == "create":
        #     await self.create(op["path"],op["content"])

        async def write(op):  
            is_append = op.get("is_append")
            if is_append is None:
                is_append = False
            return await self.write(op["path"],op["content"],is_append)
        self.add_ai_operation(SimpleAIOperation(
            op="write",
            description="write file",
            func_handler=write,
        ))

        async def delete(op):  
            return await self.delete(op["path"])
        self.add_ai_operation(SimpleAIOperation(
            op="delete",
            description="delete path",
            func_handler=delete,
        ))

        async def rename(op):  
            return await self.move(op["path"],op["new_name"])
        self.add_ai_operation(SimpleAIOperation(
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

class ShellEnvironment(SimpleEnvironment):
    def __init__(self, env_id: str) -> None:
        super().__init__(env_id)

        operator_param = {
            "command": "command will execute",
        }
        self.add_ai_function(SimpleAIFunction("shell_exec",
                                        "execute shell command in linux bash",
                                        self.shell_exec,operator_param))
        
        #run_code_param = {
        #    "pycode": "python code will execute",
        #}
        #self.add_ai_function(SimpleAIFunction("run_code",
        #                                "execute python code",
        #                                self.run_code,run_code_param))
        

    async def shell_exec(self,command:str) -> str:
        import asyncio.subprocess
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        returncode = process.returncode
        if returncode == 0:
            return f"Execute success! stdout is:\n{stdout}\n"
        else:
            return f"Execute failed! stderr is:\n{stderr}\n"


class WorkspaceEnvironment(CompositeEnvironment):
    def __init__(self, env_id: str) -> None:
        super().__init__(env_id)
        myai_path = AIStorage.get_instance().get_myai_dir() 
        self.root_path = f"{myai_path}/workspace/{env_id}"
        if not os.path.exists(self.root_path):
            os.makedirs()

        self.todo_list = {}
        self.todo_list[TodoListType.TO_WORK] = TodoListEnvironment(self.root_path,TodoListType.TO_WORK)
        self.todo_list[TodoListType.TO_LEARN] = TodoListEnvironment(self.root_path,TodoListType.TO_LEARN)

        # default environments in workspace
        self.add_env(self.todo_list[TodoListType.TO_WORK])
        self.add_env(ShellEnvironment("shell"))
        self.add_env(FilesystemEnvironment(self.root_path, "fs"))

    def set_root_path(self,path:str):
        self.root_path = path

    def get_prompt(self) -> AgentMsg:
        return None
    
    def get_role_prompt(self,role_id:str) -> AgentPrompt:
        return None

    def get_do_prompt(self,todo:AgentTodo=None)->AgentPrompt:
        return None

    # result mean: list[op_error_str],have_error
    async def exec_op_list(self,oplist:List,agent_id:str)->tuple[List[str],bool]:
        result_str = "op list is none"
        if oplist is None:
            return None,False
        
        result_str = []
        have_error = False
        for op in oplist:
            operation = self.get_ai_operation(op["op"])
            if operation:
                error_str = await operation.execute(op)
            else:
                logger.error(f"execute op list failed: unknown op:{op['op']}")
                error_str = f"execute op list failed: unknown op:{op['op']}"

            if error_str:
                have_error = True
                result_str.append(error_str)
            else:
                result_str.append(f"execute success!")  
    
        return result_str,have_error
        
