# pylint:disable=E0402
from ast import Dict
import json
import sqlite3
import os
import logging
from typing import List, Optional

import aiofiles

from ..proto.ai_function import AIFunction, ParameterDefine,SimpleAIFunction,ActionNode,SimpleAIAction
from ..proto.agent_task import AgentTask,AgentTodoTask,AgentWorkLog,AgentTaskManager
from ..storage.storage import AIStorage
from .llm_context import GlobaToolsLibrary

logger = logging.getLogger(__name__)

class LocalAgentTaskManger(AgentTaskManager):
    def __init__(self, owner_id):
        super().__init__() 
        self.root_path = f"{AIStorage.get_instance().get_myai_dir()}/tasklist/{owner_id}"
        #self.root_path = os.path.join(workspace, list_type)
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path)

        self.db_path = os.path.join(self.root_path, "tasklist.db")
        self.conn = None
        try:
            self.conn = sqlite3.connect(self.db_path)
        except Exception as e:
            logger.error("Error occurred while connecting to database: %s", e)
            return None

        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS obj_list (
                id TEXT, 
                path TEXT
            )
        ''')
        self.conn.commit()

    def _get_obj_path(self,objid:str) -> str:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT path FROM obj_list WHERE id = ?
        ''',(objid,))
        row = cursor.fetchone()
        if row:
            return row[0]
        else:
            return None
        
    def _save_obj_path(self,objid:str,path:str):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO obj_list (id,path) VALUES (?,?)
        ''',(objid,path))
        self.conn.commit()
        
    async def create_task(self,task:AgentTask,parent_id:str = None) -> str:
        try:
            #perfix = task.task_id[-5]
            if parent_id:
                parent_path = self._get_obj_path(parent_id)
                task_path = f"{parent_path}/{task.title}"
            else:
                task_path = f"{task.title}"

            dir_path = f"{self.root_path}/{task_path}"
    
            os.makedirs(dir_path)
            detail_path = f"{dir_path}/detail"
            if task.task_path is None:
                task.task_path = task_path
            self._save_obj_path(task.task_id,task_path)
            logger.info("create_task at %s",detail_path)
            async with aiofiles.open(detail_path, mode='w', encoding="utf-8") as f:
                await f.write(json.dumps(task.to_dict(),ensure_ascii=False))
            return "create task ok"
        except Exception as e:
            logger.error("create_task failed:%s",e)
            return str(e)
        


    async def create_todos(self,owner_task_id:str,todos:List[AgentTodoTask]):
        owner_task_path = self._get_obj_path(owner_task_id)
        if owner_task_path is None:
            return f"owner task {owner_task_id} not found"
        
        try:
            step_order = 0
            for todo in todos:
                todo.step_order = step_order
                todo.owner_taskid = owner_task_id
                todo_path = f"{self.root_path}/{owner_task_path}/#{step_order} {todo.title}.todo"
                self._save_obj_path(todo.todo_id,todo_path)
                async with aiofiles.open(todo_path, mode='w', encoding="utf-8") as f:
                    await f.write(json.dumps(todo.to_dict(),ensure_ascii=False))   
                logger.info("create_todos at %s OK!",todo_path)     
                step_order += 1
        except Exception as e:
            logger.error("create_todos failed:%s",e)
            return str(e)

        return None


    async def append_worklog(self,task:AgentTask,log:AgentWorkLog):
        worklog = f"{self.root_path}/{task.task_path}/.worklog"

        async with aiofiles.open(worklog, mode='w+', encoding="utf-8") as f:
            content = await f.read()
            if len(content) > 0:
                json_obj = json.loads(content)
            else:
                json_obj = {}
            logs = json_obj.get("logs")
            if logs is None:
                logs = []
            logs.append(log.to_dict())
            json_obj["logs"] = logs
            await f.write(json.dumps(json_obj,ensure_ascii=False))


    async def get_worklog(self,obj_id:str)->List[AgentWorkLog]:
        obj_path = self._get_obj_path(obj_id)
        if obj_path is None:
            return []
        
        if obj_path.endswith(".todo"):
            dir_path = os.path.dirname(obj_path)
            worklog_path = f"{self.root_path}/{dir_path}/.worklog"
        else:
            worklog_path = f"{self.root_path}/{obj_path}/.worklog"

        async with aiofiles.open(worklog_path, mode='r', encoding="utf-8") as f:
            content = await f.read()
            if len(content) > 0:
                json_obj = json.loads(content)
            else:
                json_obj = {}
            logs = json_obj.get("logs")
            return logs

 
    async def get_task(self,task_id:str) -> AgentTask:
        task_path = self._get_obj_path(task_id)
        if task_path is None:
            logger.error("get_task:%s,not found!",task_id)
            return None
        
        return await self.get_task_by_path(task_path)

    async def _get_task_by_fullpath(self,task_fullpath) -> AgentTask:
        detail_path = f"{task_fullpath}/detail"
        try:
            with open(detail_path, mode='r', encoding="utf-8") as f:
                task_dict = json.load(f)
                result_task:AgentTask =  AgentTask.from_dict(task_dict)
                if result_task:
                    relative_path = os.path.relpath(task_fullpath, self.root_path)
                    result_task.task_path = relative_path
                else:
                    logger.error("_get_task_by_fullpath:%s,parse failed!",detail_path)
                
                return result_task
        except Exception as e:
            logger.error("_get_task_by_fullpath:%s,failed:%s",task_fullpath,e)
            return None

    async def get_task_by_path(self,task_path:str) -> AgentTask:
        full_path = f"{self.root_path}/{task_path}"
        return await self._get_task_by_fullpath(full_path)
 
    async def get_todo(self,todo_id:str) -> AgentTodoTask:
        todo_path = self._get_obj_path(todo_id)
        if todo_path is None:
            logger.error("get_todo:%s,not found!",todo_id)
            return None
        
        try:
            with open(todo_path, mode='r', encoding="utf-8") as f:
                todo_dict = json.load(f)
                result_todo:AgentTodoTask =  AgentTodoTask.from_dict(todo_dict)
                if result_todo:
                    result_todo.todo_path = todo_path
                else:
                    logger.error("get_todo:%s,parse failed!",todo_path)
                
                return result_todo
        except Exception as e:
            logger.error("get_todo:%s,failed:%s",todo_path,e)
        
        return None

    async def get_sub_tasks(self,task_id:str) -> List[AgentTask]:
        task_path = self._get_obj_path(task_id)
        if task_path is None:
            return []
        
        sub_tasks = []
        for sub_item in os.listdir(task_path):
            if sub_item.startswith("."):
                continue
            if sub_item == "workspace":
                continue

            full_path = os.path.join(task_path, sub_item)
            if os.path.isdir(full_path):
                sub_task = await self.get_task_by_path(f"{task_path}/{sub_item}")
                if sub_task:
                    sub_tasks.append(sub_task)
        pass


    async def get_sub_todos(self,task_id:str) -> List[AgentTodoTask]:
        task_path = self._get_obj_path(task_id)
        if task_path is None:
            return []
        
        sub_todos = []
        for sub_item in os.listdir(task_path):
            if sub_item.startswith("."):
                continue
            if sub_item == "workspace":
                continue

            full_path = os.path.join(task_path, sub_item)
            if os.path.isfile(full_path) and sub_item.endswith(".todo"):
                sub_todo = await self.get_todo_by_path(f"{task_path}/{sub_item}")
                if sub_todo:
                    sub_todos.append(sub_todo)
        
        return sub_todos

 
    #async def get_task_depends(self,task_id:str) -> List[AgentTask]:
    #    pass

 
    async def list_task(self,filter:Optional[dict] = None ) -> List[AgentTask]:
        directory_path = self.root_path
        result_list:List[AgentTask] = []

        for entry in os.scandir(directory_path):
            if not entry.is_dir():
                continue
            if entry.name.startswith("."):
                continue
            if entry.name == "workspace":
                continue
            task_item = await self._get_task_by_fullpath(entry.path)
            if task_item:
                if not task_item.is_finish():
                    result_list.append(task_item)
        
        return result_list
        

    async def update_task(self,task:AgentTask):
        detail_path = f"{self.root_path}/{task.task_path}/detail"
        try:
            async with aiofiles.open(detail_path, mode='w', encoding="utf-8") as f:
                await f.write(json.dumps(task.to_dict(),ensure_ascii=False))
        except Exception as e:
            logger.error("update_task failed:%s",e)
            return str(e)
        
        return None

    async def update_todo(self,todo:AgentTodoTask):
        todo_path = self._get_obj_path(todo.todo_id)
        if todo_path is None:
            return f"todo {todo.todo_id} not found"
        
        try:
            async with aiofiles.open(todo_path, mode='w', encoding="utf-8") as f:
                await f.write(json.dumps(todo.to_dict(),ensure_ascii=False))
        except Exception as e:
            logger.error("update_todo failed:%s",e)
            return str(e)
        
        return None
    
    #async def update_task_state(self,task_id,state:str):
    #    pass

    #async def update_todo_state(self,task_id,state:str):
    #    pass
    
    #todo共享其所在task的文件夹

    async def get_task_file(self,task_id:str,path:str)->str:
        #return fileid
        pass
    

    async def set_task_file(self,task_id:str,path:str,fileid:str):
        pass


    async def list_task_file(self,task_id:str,path:str):
        pass


    async def remove_task_file(self,task_id:str,path:str):
        pass



class AgentWorkspace:
    def __init__(self,owner_id:str) -> None:
        self.owner_id : str = owner_id
        self.task_mgr : AgentTaskManager = LocalAgentTaskManger(owner_id)


    @staticmethod
    def register_ai_functions():
        async def create_task(params):  
            _workspace = params.get("_workspace")
            _agent_id = params.get("_agentid")
            if _workspace is None:
                return "_workspace not found"
            if params.get("creator") is None:
                params["creator"] = _agent_id
            taskObj = AgentTask.create_by_dict(params)
            parent_id = params.get("parent")
            return await _workspace.task_mgr.create_task(taskObj,parent_id)
        parameters = ParameterDefine.create_parameters({
            "title": {"type": "string", "description": "task title"},
            "detail": {"type": "string", "description": "task detail(simple task can not be filled)"},
            "tags": {"type": "string", "description": "optional,task tags"},
            "due_date": {"type": "string", "description": "optional,task due date"},
            "parent": {"type": "string", "description": "optional,parent task id"},
        })
        create_task_action = SimpleAIFunction(
            "agent.workspace.create_task",
            "Create a task",
            create_task,
            parameters,
        )
        GlobaToolsLibrary.get_instance().register_tool_function(create_task_action)

        async def cancel_task(parameters):
            _workspace = parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            task_id = parameters.get("task_id")
            task = await _workspace.task_mgr.get_task(task_id)
            if task is None:
                return f"task {task_id} not found"
            task.state = "cancel"
            await _workspace.task_mgr.update_task(task)
            return "canncel task ok"
        
        parameters = ParameterDefine.create_parameters({
            "task_id": {"type": "string", "description": "task id which want to cancel"},
        })
        cancel_task_action = SimpleAIFunction(
            "agent.workspace.cancel_task",
            "Cancel this task",
            cancel_task,
            parameters
        )
        GlobaToolsLibrary.get_instance().register_tool_function(cancel_task_action)


        async def list_task(parameters):
            _workspace = parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            all_task = await _workspace.task_mgr.list_task(None)
            if all_task:
                return json.dumps([task.to_dict() for task in all_task],ensure_ascii=False)
            else :
                return "no task"
        list_task_ai_function = SimpleAIFunction("agent.workspace.list_task",
                                              "list all tasks in json format",
                                               list_task,{})
        GlobaToolsLibrary.get_instance().register_tool_function(list_task_ai_function)
        