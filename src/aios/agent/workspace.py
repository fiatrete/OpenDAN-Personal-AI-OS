# pylint:disable=E0402
from ast import Dict
import json
import sqlite3
import os
import glob
import time
from typing import List, Optional
import aiofiles

from  ..proto.agent_msg import AgentMsg
from ..proto.ai_function import AIFunction, ParameterDefine,SimpleAIFunction,ActionNode,SimpleAIAction
from ..proto.agent_task import AgentTask, AgentTaskState,AgentTodo,AgentWorkLog,AgentTaskManager
from ..storage.storage import AIStorage
from ..frame.bus import AIBus
from .llm_context import GlobaToolsLibrary

import logging
logger = logging.getLogger(__name__)

class LocalAgentTaskManger(AgentTaskManager):
    def __init__(self, owner_id):
        super().__init__() 
        self.root_path = f"{AIStorage.get_instance().get_myai_dir()}/agent_data/{owner_id}/workspace/"
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
        


    async def set_todos(self,owner_task_id:str,todos:List[Dict]):
        owner_task_path = self._get_obj_path(owner_task_id)
        if owner_task_path is None:
            return f"owner task {owner_task_id} not found"
        
        try:
            directory = f"{self.root_path}/{owner_task_path}"
            file_extension = "*.todo"
            pattern = os.path.join(directory, file_extension)
            files = glob.glob(pattern)

            for file in files:
                os.remove(file)
                logger.info(f"Deleted {file}")
        except Exception as e:
            logger.error("set_todos deleted todos failed:%s",e)

        try:
            step_order = 0
            for todo in todos:
                todo_obj = AgentTodo.from_dict(todo)
                todo_obj.step_order = step_order
                todo_obj.owner_taskid = owner_task_id
                todo_path = f"{self.root_path}/{owner_task_path}/#{step_order} {todo_obj.title}.todo"
                self._save_obj_path(todo_obj.todo_id,todo_path)
                async with aiofiles.open(todo_path, mode='w', encoding="utf-8") as f:
                    await f.write(json.dumps(todo_obj.to_dict(),ensure_ascii=False))   
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
 
    async def get_todo(self,todo_id:str) -> AgentTodo:
        todo_path = self._get_obj_path(todo_id)
        if todo_path is None:
            logger.error("get_todo:%s,not found!",todo_id)
            return None
        
        try:
            with open(todo_path, mode='r', encoding="utf-8") as f:
                todo_dict = json.load(f)
                result_todo:AgentTodo =  AgentTodo.from_dict(todo_dict)
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
        task_path = f"{self.root_path}/{task_path}"
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
        
        return sub_tasks


    async def get_sub_todos(self,task_id:str) -> List[AgentTodo]:
        task_path = self._get_obj_path(task_id)
        if task_path is None:
            return []
        task_path = f"{self.root_path}/{task_path}"
        sub_todos = []
        for sub_item in os.listdir(task_path):
            if sub_item.startswith("."):
                continue
            if sub_item == "workspace":
                continue
            if sub_item == "details":
                continue

            full_path = os.path.join(task_path, sub_item)
            if os.path.isfile(full_path) and sub_item.endswith(".todo"):
                sub_todo = await self.get_todo_by_path(full_path)
                if sub_todo:
                    sub_todos.append(sub_todo)
        
        return sub_todos

    async def get_todo_by_path(self,todo_path:str) -> AgentTodo:
        async with aiofiles.open(todo_path, mode='r', encoding="utf-8") as f:
            s = await f.read()
            todo_dict = json.loads(s)
            result_todo:AgentTodo =  AgentTodo.from_dict(todo_dict)
            if result_todo:
                result_todo.todo_path = todo_path
            else:
                logger.error("get_todo_by_path:%s,parse failed!",todo_path)
            
            return result_todo

    #async def get_task_depends(self,task_id:str) -> List[AgentTask]:
    #    pass

 
    async def list_task(self,filter:Optional[dict] = None ) -> List[AgentTask]:
        directory_path = self.root_path
        result_list:List[AgentTask] = []
        special_state = None
        if filter:
            special_state = filter.get("state")
            #agent_id = filter.get("agent_id")

        for entry in os.scandir(directory_path):
            if not entry.is_dir():
                continue
            if entry.name.startswith("."):
                continue
            if entry.name == "workspace":
                continue
            task_item = await self._get_task_by_fullpath(entry.path)
            if task_item:
                if filter is None:
                    if task_item.is_finish():
                        continue
                
                if special_state:
                    if task_item.state != special_state:
                        continue

                
                result_list.append(task_item)
        
        return result_list
        

    async def update_task(self,task:AgentTask):
        detail_path = f"{self.root_path}/{task.task_path}/detail"
        try:
            new_task_content = json.dumps(task.to_dict(),ensure_ascii=False)
            async with aiofiles.open(detail_path, mode='w', encoding="utf-8") as f:
                await f.write(new_task_content)
        except Exception as e:
            logger.error("update_task failed:%s",e)
            return str(e)
        
        return None

    async def update_todo(self,todo:AgentTodo):
        todo_path = self._get_obj_path(todo.todo_id)
        if todo_path is None:
            return f"todo {todo.todo_id} not found"
        
        try:
            new_todo_content = json.dumps(todo.to_dict(),ensure_ascii=False)
            async with aiofiles.open(todo_path, mode='w', encoding="utf-8") as f:
                await f.write(new_todo_content)
        except Exception as e:
            logger.error("update_todo failed:%s",e)
            return str(e)
        
        return None
    
    #async def update_task_state(self,task_id,state:str):
    #    pass

    #async def update_todo_state(self,task_id,state:str):
    #    pass
    
    #todo共享其所在task的文件夹
    # if task_id is none, means root folder in workspace
    def _get_taskfile_path(self,task_id:str,path:str)->str:
        root_path = self.root_path
        if task_id is None:
            root_path = f"{root_path}/workspace"
        else:
            task_path = self._get_obj_path(task_id)
            if task_path is None:
                return None
            root_path = f"{task_path}/wrorkspace"
        
        file_path = f"{root_path}/{path}"
        return file_path

    async def read_task_file(self,task_id:str,path:str)->str:
        file_path = self._get_taskfile_path(task_id,path)
        if not os.path.exists(file_path):
            return None
        
        try:
            async with aiofiles.open(file_path, mode='r', encoding="utf-8") as f:
                content = await f.read()
                return content
        except Exception as e:
            logger.error("read_task_file failed:%s",e)
            return None    
        
    
    async def write_task_file(self,task_id:str,path:str,content:str):
        file_path = self._get_taskfile_path(task_id,path)
        # write file
        try:
            dir_name = os.path.dirname(file_path)
            os.makedirs(dir_name)
            async with aiofiles.open(file_path, mode='w', encoding="utf-8") as f:
                await f.write(content)
        except Exception as e:
            logger.error("write_task_file failed:%s",e)
            return str(e)
        
    async def append_task_file(self,task_id:str,path:str,content:str):
        file_path = self._get_taskfile_path(task_id,path)
        # append file
        try:
            async with aiofiles.open(file_path, mode='a', encoding="utf-8") as f:
                await f.write(content)
        except Exception as e:
            logger.error("append_task_file failed:%s",e)
            return str(e)


    async def list_task_dir(self,task_id:str,path:str) -> List[str]:
        dir_path = self._get_taskfile_path(task_id,path)
        if not os.path.exists(dir_path):
            return None
        
        try:
            result_node = os.listdir(dir_path)
            result = []
            for name in result_node:
                if name.startswith("."):
                    continue

                result.append(name)
            return result
        except Exception as e:
            logger.error("list_task_dir failed:%s",e)
            return None
    

    async def remove_task_file(self,task_id:str,path:str):
        file_path = self._get_taskfile_path(task_id,path)
        try:
            os.remove(file_path)
        except Exception as e:
            logger.error("remove_task_file failed:%s",e)
            return str(e)
        
        return None



class AgentWorkspace:
    def __init__(self,owner_id:str) -> None:
        self.owner_id : str = owner_id
        self.task_mgr : AgentTaskManager = LocalAgentTaskManger(owner_id)

    @staticmethod
    def register_ai_functions():
        async def post_message(parameters):
            _agent_id = parameters.get("_agentid")
            if _agent_id is None:
                return "_agentid not found"

            target = parameters.get("target")
            if target is None:
                return "target not found"
            message = parameters.get("message")
            if message is None:
                return "message not found"
            topic = parameters.get("topic")

            msg = AgentMsg()
            msg.sender = _agent_id
            msg.body = message
            msg.topic = topic
            msg.target = target
            msg.create_time = time.time()   
            
            is_post_ok = await AIBus.get_default_bus().post_message(msg)
            if is_post_ok:
                return "post message ok!"
            else:
                return f"post message to {target} failed!"
        
        parameters = ParameterDefine.create_parameters({
            "target": {"type": "string", "description": "target agent/contact fullname or telephone or email"},
            "topic": {"type": "string", "description": "optional, message topic"},
            "message": {"type": "string", "description": "message content"},
        })
        post_message_action = SimpleAIFunction(
            "post_message",
            "Post a message to target agent/contact",
            post_message,
            parameters,
        )
        GlobaToolsLibrary.get_instance().register_tool_function(post_message_action)

        async def send_message(parameters):
            _agent_id = parameters.get("_agentid")
            if _agent_id is None:
                return "_agentid not found"

            target = parameters.get("target")
            if target is None:
                return "target not found"
            message = parameters.get("message")
            if message is None:
                return "message not found"
            topic = parameters.get("topic")

            msg = AgentMsg()
            msg.sender = _agent_id
            msg.body = message
            msg.topic = topic
            msg.target = target
            msg.create_time = time.time()   
            
            resp = await AIBus.get_default_bus().send_message(msg)
            if resp:
                return f"resp is :  {resp.body}"
            else:
                return f"send message to {target} failed!"
        
        parameters = ParameterDefine.create_parameters({
            "target": {"type": "string", "description": "target agent/contact id"},
            "topic": {"type": "string", "description": "optional, message topic"},
            "message": {"type": "string", "description": "message content"},
        })
        send_message_action = SimpleAIFunction(
            "send_message",
            "send a message to target agent/contact, and wait for reply",
            send_message,
            parameters,
        )
        GlobaToolsLibrary.get_instance().register_tool_function(send_message_action)

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
            "title" : {"type": "string", "description": "task title,Simple and clear, try to include the task \ Related personnel \ place \ key conditions \ time element involved in the event"},
            "detail" : {"type": "string", "description": "task detail(simple task can not be filled)"},
            "priority" : {"type": "int", "description": "task priority from 1-10"},
            #"due_date": {"type": "isoformat time string", "description": "optional,confirm task due date"},
            #"expiration_time": {"type": "isoformat time string", "description": "optional,confirm task expiration time"},
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
            task : AgentTask = await _workspace.task_mgr.get_task(task_id)
            if task is None:
                return f"task {task_id} not found"
            task.state = AgentTaskState.TASK_STATE_CANCEL
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


        async def confirm_task(parameters):
            _workspace = parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            task_id = parameters.get("task_id")
            task : AgentTask = await _workspace.task_mgr.get_task(task_id)
            if task is None:
                return f"task {task_id} not found"
            if parameters.get("priority"):
                task.priority = parameters.get("priority")
            if parameters.get("next_attention_time"):
                task.next_attention_time = parameters.get("next_attention_time")
            if parameters.get("expiration_time"):
                task.expiration_time = parameters.get("expiration_time")
            if parameters.get("due_date"):
                task.due_date = parameters.get("due_date")
            task.state = AgentTaskState.TASK_STATE_CONFIRMED
            await _workspace.task_mgr.update_task(task)
            return "confirm task ok"
        parameters = ParameterDefine.create_parameters({
            "task_id": {"type": "string", "description": "task id which want to confirm"},
            "next_attention_time": {"type": "isoformat time string", "description": "optional,confirm task next attention time"},
            "expiration_time": {"type": "isoformat time string", "description": "optional,confirm task expiration time"},
            #"due_date": {"type": "isoformat time string", "description": "optional,confirm task due date"},
            "priority": {"type": "int", "description": "optional,task priority from 1-10"},
        })
        confirm_task_action = SimpleAIFunction(
            "agent.workspace.confirm_task",
            "After understanding the content of the task, the importance of the importance of the task, the priority, the deadline, etc.",
            confirm_task,
            parameters
        )
        GlobaToolsLibrary.get_instance().register_tool_function(confirm_task_action)

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
        
        async def update_task(parameters):
            _workspace : AgentWorkspace= parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            task_id = parameters.get("task_id")
            task:AgentTask = await _workspace.task_mgr.get_task(task_id)
            if task is None:
                return f"task {task_id} not found"
            if parameters.get("title"):
                task.title = parameters.get("title")
            if parameters.get("detail"):
                task.detail = parameters.get("detail")
            if parameters.get("priority"):
                task.priority = parameters.get("priority")
            if parameters.get("new_state"):
                task.state = AgentTaskState.from_str(parameters.get("new_state"))
            if parameters.get("next_attention_time"):
                task.next_attention_time = parameters.get("next_attention_time")
            if parameters.get("due_date"):
                task.due_date = parameters.get("due_date")
            if parameters.get("expiration_time"):
                task.expiration_time = parameters.get("expiration_time")
            await _workspace.task_mgr.update_task(task)
            return "update task ok"
        parameters = ParameterDefine.create_parameters({
            "task_id": {"type": "string", "description": "task id which want to update"},
            "new_state": {"type": "string", "description": "optional,new task state: cancel or done"},
            "next_attention_time": {"type": "isoformat time string", "description": "optional,update task next attention time"},
            "expiration_time": {"type": "isoformat time string", "description": "optional,update task expiration time"},
            "priority": {"type": "int", "description": "optional,task priority from 1-10"},
            "title": {"type": "string", "description": "optional, new task title"},
            "detail": {"type": "string", "description": "optional, new task detail(simple task can not be filled)"},
            #"due_date": {"type": "string", "description": "optional,new task due date"},
        })
        update_task_ai_function = SimpleAIFunction("agent.workspace.update_task",
                                              "update task to new state",
                                               update_task,parameters)
        GlobaToolsLibrary.get_instance().register_tool_function(update_task_ai_function)

        async def set_todos(parameters):
            _workspace : AgentWorkspace= parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            task_id = parameters.get("task_id")
            task:AgentTask = await _workspace.task_mgr.get_task(task_id)
            if task is None:
                return f"task {task_id} not found"
            todos = parameters.get("todos")
            if todos is None:
                return "todos not found"
            await _workspace.task_mgr.set_todos(task_id,todos)
            return "set todos ok"
        
        todo_demo = """
        [
            {
                "title": "todo1",
                "detail": "todo1 detail",
                "tags": "tag1,tag2",
                "due_date": "2021-01-01",
                "priority": 1
            },
        ]
        """
        parameters = ParameterDefine.create_parameters({
            "task_id": {"type": "string", "description": "task id which want to set todos"},
            "todos": {"type": "list", "description": f"List of todo, todo is a dict like {todo_demo}"},
        })
        set_todos_ai_function = SimpleAIFunction("agent.workspace.set_todos",
                                              "set todos for task",
                                               set_todos,parameters)
        GlobaToolsLibrary.get_instance().register_tool_function(set_todos_ai_function)

        async def update_todo(parameters):
            _workspace : AgentWorkspace= parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            todo_id = parameters.get("todo_id")
            todo : AgentTodo = await _workspace.task_mgr.get_todo(todo_id)
            if todo is None:
                return f"todo {todo_id} not found"
            
        parameters = ParameterDefine.create_parameters({
            "todo_id": {"type": "string", "description": "todo id which want to update"},
            "new_state": {"type": "string", "description": "optional,new todo state: execute_ok , execute_failed, done or check_failed"},
        })    
        update_todo_ai_function = SimpleAIFunction("agent.workspace.update_todo",
                                              "update todo to new state",
                                               update_todo,parameters)
        GlobaToolsLibrary.get_instance().register_tool_function(update_todo_ai_function)


        # write file
        async def write_task_file(parameters):
            _workspace : AgentWorkspace= parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            task_id = parameters.get("task_id")
            path = parameters.get("filename")
            content = parameters.get("content")
            await _workspace.task_mgr.write_task_file(task_id,path,content)
            return "write task file ok"
        parameters = ParameterDefine.create_parameters({
            "filename": {"type": "string", "description": "filename"},
            "content": {"type": "string", "description": "file content"},
        })
        write_task_file_ai_function = SimpleAIFunction("agent.workspace.write_file",
                                              "write file for task",
                                               write_task_file,parameters)
        GlobaToolsLibrary.get_instance().register_tool_function(write_task_file_ai_function)

        # append file
        async def append_task_file(parameters):
            _workspace : AgentWorkspace= parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            task_id = parameters.get("task_id")
            path = parameters.get("filename")
            content = parameters.get("content")
            await _workspace.task_mgr.append_task_file(task_id,path,content)
            return "append task file ok"
        parameters = ParameterDefine.create_parameters({
            "filename": {"type": "string", "description": "filename"},
            "content": {"type": "string", "description": "file content"},
        })
        append_task_file_ai_function = SimpleAIFunction("agent.workspace.append_file",
                                              "append file for task",
                                               append_task_file,parameters)
        GlobaToolsLibrary.get_instance().register_tool_function(append_task_file_ai_function)

        # read file
        async def read_task_file(parameters):
            _workspace : AgentWorkspace= parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            task_id = parameters.get("task_id")
            path = parameters.get("filename")
            content = await _workspace.task_mgr.read_task_file(task_id,path)
            return content
        parameters = ParameterDefine.create_parameters({
            "filename": {"type": "string", "description": "filename"},
        })
        read_task_file_ai_function = SimpleAIFunction("agent.workspace.read_file",
                                              "read file for task",
                                               read_task_file,parameters)
        GlobaToolsLibrary.get_instance().register_tool_function(read_task_file_ai_function)

        # list dir
        async def list_task_dir(parameters):
            _workspace : AgentWorkspace= parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            task_id = parameters.get("task_id")
            path = parameters.get("path")
            content = await _workspace.task_mgr.list_task_dir(task_id,path)
            return content
        parameters = ParameterDefine.create_parameters({
            "path": {"type": "string", "description": "The relative path of the dir"},
        })
        list_task_dir_ai_function = SimpleAIFunction("agent.workspace.list_dir",
                                              "list dir in task workspace",
                                               list_task_dir,parameters)
        GlobaToolsLibrary.get_instance().register_tool_function(list_task_dir_ai_function)

        # remove file
        async def remove_task_file(parameters):
            _workspace : AgentWorkspace= parameters.get("_workspace")
            if _workspace is None:
                return "_workspace not found"
            task_id = parameters.get("task_id")
            path = parameters.get("filename")
            content = await _workspace.task_mgr.remove_task_file(task_id,path)
            return content
        parameters = ParameterDefine.create_parameters({
            "filename": {"type": "string", "description": "filename"},
        })
        remove_task_file_ai_function = SimpleAIFunction("agent.workspace.remove_file",
                                              "remove file for task",
                                               remove_task_file,parameters)
        GlobaToolsLibrary.get_instance().register_tool_function(remove_task_file_ai_function)


        
