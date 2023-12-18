# pylint:disable=E0402
import json
import logging
import os
import aiofiles
import sqlite3
import asyncio
from typing import Any,List,Dict
import chardet

from ..proto.agent_task import *
from ..proto.ai_function import *
from ..proto.compute_task import *
from ..agent.agent_base import *

from ..storage.storage import AIStorage,ResourceLocation
from .environment import SimpleEnvironment, CompositeEnvironment


logger = logging.getLogger(__name__)

class TodoListType:
    TO_WORK = "work"
    TO_LEARN = "learn"

class TodoListEnvironment(SimpleEnvironment):
    def __init__(self, workspace, list_type) -> None:
        super().__init__(workspace)
        self.root_path = os.path.join(workspace, list_type)
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)

        self.db_path = os.path.join(self.root_path, "todo.db")
        self.conn = None
        try:
            self.conn = sqlite3.connect(self.db_path)
        except Exception as e:
            logger.error("Error occurred while connecting to database: %s", e)
            return None

        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS todo_list (
                id TEXT, 
                path TEXT
            )
        ''')
        self.conn.commit()

        async def create_todo(params):  
            todoObj = AgentTodo.from_dict(params["todo"])
            parent_id = params.get("parent")
            return await self.create_todo(parent_id,todoObj)
        
        self.add_ai_operation(SimpleAIAction(
            op="create_todo",
            description="create todo",
            func_handler=create_todo,
        ))


        async def update_todo(params):
            todo_id = params["id"]
            new_stat = params["state"]
            return await self.update_todo(todo_id,new_stat)
        
        self.add_ai_operation(SimpleAIAction(
            op="update_todo",
            description="update todo",
            func_handler=update_todo,
        ))

    def _get_todo_path(self,todo_id:str) -> str:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT path FROM todo_list WHERE id = ?
        ''',(todo_id,))
        row = cursor.fetchone()
        if row:
            return row[0]
        else:
            return None

    def _save_todo_path(self,todo_id:str,path:str):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO todo_list (id,path) VALUES (?,?)
        ''',(todo_id,path))
        self.conn.commit()
 
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
            with open(detail_path, mode='r', encoding="utf-8") as f:
                todo_dict = json.load(f)
                result_todo =  AgentTodo.from_dict(todo_dict)
                if result_todo:
                    relative_path = os.path.relpath(path, self.root_path)
                    if not relative_path.startswith('/'):
                        relative_path = '/' + relative_path
                    result_todo.todo_path = relative_path
                else:
                    logger.error("get_todo_by_path:%s,parse failed!",path)
                
                return result_todo
        except Exception as e:
            logger.error("get_todo_by_path:%s,failed:%s",path,e)
            return None


    async def create_todo(self,parent_id:str,todo:AgentTodo) -> str:
        try:
            if parent_id:
                parent_path = self._get_todo_path(parent_id)
                todo_path = f"{parent_path}/{todo.todo_id}-{todo.title}"
            else:
                todo_path = f"{todo.todo_id}-{todo.title}"

            dir_path = f"{self.root_path}/{todo_path}"
    
            os.makedirs(dir_path)
            detail_path = f"{dir_path}/detail"
            if todo.todo_path is None:
                todo.todo_path = todo_path
            self._save_todo_path(todo.todo_id,todo_path)
            logger.info("create_todo %s",detail_path)
            async with aiofiles.open(detail_path, mode='w', encoding="utf-8") as f:
                await f.write(json.dumps(todo.to_dict()))
        except Exception as e:
            logger.error("create_todo failed:%s",e)
            return str(e)
        
        return None

    async def update_todo(self,todo_id:str,new_stat:str)->str:
        try:
            todo_path = self._get_todo_path(todo_id)
            full_path = f"{self.root_path}/{todo_path}"
            todo : AgentTodo = await self.get_todo_by_fullpath(full_path)
            if todo:
                todo.state = new_stat
                detail_path =  f"{full_path}/detail"
                async with aiofiles.open(detail_path, mode='w', encoding="utf-8") as f:
                    await f.write(json.dumps(todo.to_dict()))
                    return None
            else:
                return "todo not found."
        except Exception as e:
            return str(e)
    
    async def wait_todo_done(self,todo_id:str,state=AgentTodo.TODO_STATE_WAITING_CHECK) -> AgentTodo:
        todo_path = self._get_todo_path(todo_id)
        full_path = f"{self.root_path}/{todo_path}"
        async def check_done():
            while True:
                todo : AgentTodo = await self.get_todo_by_fullpath(full_path)
                if todo is None:
                    continue
                if todo.state == AgentTodo.TODO_STATE_CANCEL:
                    break
                elif todo.state == AgentTodo.TODO_STATE_EXPIRED:
                    break
                elif todo.state == AgentTodo.TODO_STATE_WAITING_CHECK:
                    if state == AgentTodo.TODO_STATE_WAITING_CHECK:
                        break
                elif todo.state == AgentTodo.TODO_STATE_DONE:
                    if state == AgentTodo.TODO_STATE_WAITING_CHECK:
                        break
                    elif todo.state == AgentTodo.TODO_STATE_DONE:
                        break
                elif todo.state == AgentTodo.TODO_STATE_REVIEWED:
                    break
                await asyncio.sleep(1)
        
        await check_done()
        return await self.get_todo_by_fullpath(full_path)
        
    
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


class WorkspaceEnvironment(CompositeEnvironment):
    def __init__(self, env_id: str) -> None:
        myai_path = AIStorage.get_instance().get_myai_dir() 
        root_path = f"{myai_path}/workspace/{env_id}"
        super().__init__(root_path)

        self.root_path = root_path
        if not os.path.exists(self.root_path):
            os.makedirs()

        self.todo_list: Dict[str, TodoListEnvironment] = {}
        self.todo_list[TodoListType.TO_WORK] = TodoListEnvironment(self.root_path,TodoListType.TO_WORK)
        self.todo_list[TodoListType.TO_LEARN] = TodoListEnvironment(self.root_path,TodoListType.TO_LEARN)

        # default environments in workspace
        self.add_env(self.todo_list[TodoListType.TO_WORK])

    def set_root_path(self,path:str):
        self.root_path = path

    def get_prompt(self) -> AgentMsg:
        return None
    
    def get_role_prompt(self,role_id:str) -> LLMPrompt:
        return None

    def get_do_prompt(self,todo:AgentTodo=None)->LLMPrompt:
        return None

    # result mean: list[op_error_str],have_error
    async def exec_op_list(self,oplist:List,agent_id:str)->tuple[List[str],bool]:
        result_str = "op list is none"
        if oplist is None or len(oplist) == 0:
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
        
