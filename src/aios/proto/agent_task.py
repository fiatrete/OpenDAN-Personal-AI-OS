# pylint:disable=E0402
from abc import ABC, abstractmethod
from typing import List, Optional
import datetime
import time
import uuid
from anyio import Path
import logging
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

class AgentTodoResult:
    TODO_RESULT_CODE_OK = 0,
    TODO_RESULT_CODE_LLM_ERROR = 1,
    TODO_RESULT_CODE_EXEC_OP_ERROR = 2


    def __init__(self) -> None:
        self.result_code = AgentTodoResult.TODO_RESULT_CODE_OK
        self.result_str = None
        self.error_str = None
        self.op_list = None

    def to_dict(self) -> dict:
        result = {}
        result["result_code"] = self.result_code
        result["result_str"] = self.result_str
        result["error_str"] = self.error_str
        result["op_list"] = self.op_list
        return result




class AgentTodo:
    TODO_STATE_WAIT_ASSIGN = "wait_assign"
    TODO_STATE_INIT = "init"

    TODO_STATE_PENDING = "pending"
    TODO_STATE_WAITING_CHECK = "wait_check"
    TODO_STATE_EXEC_FAILED = "exec_failed"
    TDDO_STATE_CHECKFAILED = "check_failed"

    TODO_STATE_CASNCEL = "cancel"
    TODO_STATE_DONE = "done"
    TODO_STATE_EXPIRED = "expired"

    def __init__(self):
        self.todo_id = "todo#" + uuid.uuid4().hex
        self.title = None
        self.detail = None
        self.todo_path = None # get parent todo,sub todo by path
        #self.parent = None
        self.create_time = time.time()

        self.state = "wait_assign"
        self.worker = None
        self.checker = None
        self.createor = None

        self.need_check = True
        self.due_date = time.time() + 3600 * 24 * 2
        self.last_do_time = None
        self.last_check_time = None
        self.last_review_time = None

        self.depend_todo_ids = []
        self.sub_todos = {}

        self.result : AgentTodoResult = None
        self.last_check_result = None
        self.retry_count = 0
        self.raw_obj = None


    @classmethod
    def from_dict(cls,json_obj:dict) -> 'AgentTodo':
        todo = AgentTodo()
        if json_obj.get("id") is not None:
            todo.todo_id = json_obj.get("id")

        todo.title = json_obj.get("title")
        todo.state = json_obj.get("state")
        create_time = json_obj.get("create_time")
        if create_time:
            todo.create_time = datetime.fromisoformat(create_time).timestamp()

        todo.detail = json_obj.get("detail")
        due_date = json_obj.get("due_date")
        if due_date:
            todo.due_date = datetime.fromisoformat(due_date).timestamp()

        last_do_time = json_obj.get("last_do_time")
        if last_do_time:
            todo.last_do_time = datetime.fromisoformat(last_do_time).timestamp()
        last_check_time = json_obj.get("last_check_time")
        if last_check_time:
            todo.last_check_time = datetime.fromisoformat(last_check_time).timestamp()
        last_review_time = json_obj.get("last_review_time")
        if last_review_time:
            todo.last_review_time = datetime.fromisoformat(last_review_time).timestamp()

        todo.depend_todo_ids = json_obj.get("depend_todo_ids")
        todo.need_check = json_obj.get("need_check")
        #todo.result = json_obj.get("result")
        #todo.last_check_result = json_obj.get("last_check_result")
        todo.worker = json_obj.get("worker")
        todo.checker = json_obj.get("checker")
        todo.createor = json_obj.get("createor")
        if json_obj.get("retry_count"):
            todo.retry_count = json_obj.get("retry_count")

        todo.raw_obj = json_obj

        return todo

    def to_dict(self) -> dict:
        if self.raw_obj:
            result = self.raw_obj
        else:
            result = {}

        result["id"] = self.todo_id
        #result["parent_id"] = self.parent_id
        result["title"] = self.title
        result["state"] = self.state
        result["create_time"] = datetime.fromtimestamp(self.create_time).isoformat()
        result["detail"] = self.detail
        result["due_date"] = datetime.fromtimestamp(self.due_date).isoformat()
        result["last_do_time"] = datetime.fromtimestamp(self.last_do_time).isoformat() if self.last_do_time else None
        result["last_check_time"] = datetime.fromtimestamp(self.last_check_time).isoformat() if self.last_check_time else None
        result["last_review_time"] = datetime.fromtimestamp(self.last_review_time).isoformat() if self.last_review_time else None
        result["depend_todo_ids"] = self.depend_todo_ids
        result["need_check"] = self.need_check
        result["worker"] = self.worker
        result["checker"] = self.checker
        result["createor"] = self.createor
        result["retry_count"] = self.retry_count

        return result

    def can_check(self)->bool:
        if self.state != AgentTodo.TODO_STATE_WAITING_CHECK:
            return False

        now = datetime.now().timestamp()
        if self.last_check_time:
            time_diff = now - self.last_check_time
            if time_diff < 60*15:
                logger.info(f"todo {self.title} is already checked, ignore")
                return False

        return True

    def can_do(self) -> bool:
        match self.state:
            case AgentTodo.TODO_STATE_DONE:
                logger.info(f"todo {self.title} is done, ignore")
                return False
            case AgentTodo.TODO_STATE_CASNCEL:
                logger.info(f"todo {self.title} is cancel, ignore")
                return False
            case AgentTodo.TODO_STATE_EXPIRED:
                logger.info(f"todo {self.title} is expired, ignore")
                return False
            case AgentTodo.TODO_STATE_EXEC_FAILED:
                if self.retry_count > 3:
                    logger.info(f"todo {self.title} retry count ({self.retry_count}) is too many, ignore")
                    return False

        now = datetime.now().timestamp()
        time_diff = self.due_date - now
        if time_diff < 0:
            logger.info(f"todo {self.title} is expired, ignore")
            self.state = AgentTodo.TODO_STATE_EXPIRED
            return False

        if time_diff > 7*24*3600:
            logger.info(f"todo {self.title} is far before due date, ignore")
            return False

        if self.last_do_time:
            time_diff = now - self.last_do_time
            if time_diff < 60*15:
                logger.info(f"todo {self.title} is already do ignore")
                return False

        logger.info(f"todo {self.title} can do.")
        return True
    
############################################################################################
class AgentTaskState(Enum):
    TASK_STATE_WAIT= "wait_assign"
    TASK_STATE_ASSIGNED  = "assigned"
    TASK_STATE_CONFIRMED = "confirmed"

    TASK_STATE_CANCEL = "cancel"
    TASK_STATE_EXPIRED = "expired"

    TASK_STATE_DOING = "doing"
    TASK_STATE_WAITING_CHECK = "wait_check"
    TASK_STATE_CHECKFAILED = "check_failed"
    TASK_STATE_DONE = "done"
    TASK_STATE_FAILED = "failed"
    @staticmethod
    def from_str(value):
        return next((s for s in AgentTaskState.__members__.values() if s.value == value), None)

class AgentTodoState(Enum):
    TODO_STATE_WAITING = "waiting"
    TODO_STATE_WORKING = "working"
    TODO_STATE_WAIT_CHECK = "wait_check"
    TODO_STATE_CHECK_FAILED = "check_failed" 
    TODO_STATE_DONE = "done"
    TASK_STATE_FAILED = "failed"

    @staticmethod
    def from_str(value):
        return next((s for s in AgentTodoState.__members__.values() if s.value == value), None)

class AgentTodoTask:
    def __init__(self) -> None:
        self.todo_id = "todo#" + uuid.uuid4().hex
        self.todo_path : str = None
        self.owner_taskid = None
        self.name:str = None
        self.detail:str = None
        self.state = AgentTodoState.TODO_STATE_WAITING
        self.category = None
        self.step_order:int = 0

    def to_dict(self) -> dict:
        pass

    def from_dict(self,json_obj:dict) -> 'AgentTask':
        pass  

class AgentTask:
    def __init__(self) -> None:
        self.task_id : str = "task#" + uuid.uuid4().hex
        self.task_path : str = None # get parent todo,sub todo by path
        self.title = None
        self.detail = None
        self.state = AgentTaskState.TASK_STATE_WAIT
        self.priority:int = 5 # 1-10
        self.tags:List[str] = []
        self.worker = None
        self.createor = None

        # if due_date is none ,means no due date
        self.due_date = time.time() + 3600 * 24 * 2
        # 确定的执行时间（执行条件）
        self.next_do_time = None
        # 如果next check time设置，说明任务适合在该时间点可能具备执行调教，尝试检查并执行
        self.next_check_time = None

        self.depend_task_ids = []
        #self.step_todo_ids = []

        self.create_time = time.time()
        self.done_time = None

        self.last_do_time = None
        self.last_plan_time = None
        self.last_check_time = None
        #self.last_review_time = None

    def is_finish(self) -> bool:
        if self.state == AgentTaskState.TASK_STATE_DONE:
            return True
        
        if self.state == AgentTaskState.TASK_STATE_CANCEL:
            return True
        
        if self.state == AgentTaskState.TASK_STATE_EXPIRED:
            return True
        
        if self.state == AgentTaskState.TASK_STATE_FAILED:
            return True
        return False

    def to_dict(self) -> dict:
        result = {}
        result["task_id"] = self.task_id
        result["title"] = self.title
        result["detail"] = self.detail 
        result["state"] = self.state.value
        result["priority"] = self.priority
        result["tags"] = self.tags
        result["worker"] = self.worker
        result["createor"] = self.createor
        if self.due_date:
            result["due_date"] = datetime.fromtimestamp(self.due_date).isoformat()
        if self.next_do_time:
            result["next_do_time"] = datetime.fromtimestamp(self.next_do_time).isoformat()
        if self.next_check_time:
            result["next_check_time"] = datetime.fromtimestamp(self.next_check_time).isoformat()
        result["depend_task_ids"] = self.depend_task_ids
        #result["step_todo_ids"] = self.step_todo_ids
        result["create_time"] = datetime.fromtimestamp(self.create_time).isoformat()
        if self.done_time:
            result["done_time"] = datetime.fromtimestamp(self.done_time).isoformat()
        if self.last_do_time:
            result["last_do_time"] = datetime.fromtimestamp(self.last_do_time).isoformat() 
        if self.last_plan_time:
            result["last_plan_time"] = datetime.fromtimestamp(self.last_plan_time).isoformat()
        if self.last_check_time:
            result["last_check_time"] = datetime.fromtimestamp(self.last_check_time).isoformat()

        return result
    @classmethod
    def from_dict(cls,json_obj:dict) -> 'AgentTask':
        result = AgentTask()
        result.task_id = json_obj.get("task_id")
        result.title = json_obj.get("title")
        result.detail = json_obj.get("detail")
        result.state = AgentTaskState.from_str(json_obj.get("state"))
        result.priority = json_obj.get("priority")
        result.tags = json_obj.get("tags")
        result.worker = json_obj.get("worker")
        result.createor = json_obj.get("createor")
        due_date = json_obj.get("due_date")
        if due_date:
            result.due_date = datetime.fromisoformat(due_date).timestamp()
        next_do_time = json_obj.get("next_do_time")
        if next_do_time:
            result.next_do_time = datetime.fromisoformat(next_do_time).timestamp()
        next_check_time = json_obj.get("next_check_time")
        if next_check_time:
            result.next_check_time = datetime.fromisoformat(next_check_time).timestamp()
        result.depend_task_ids = json_obj.get("depend_task_ids")
        #result.step_todo_ids = json_obj.get("step_todo_ids")
        create_time = json_obj.get("create_time")
        if create_time:
            result.create_time = datetime.fromisoformat(create_time).timestamp()
        done_time = json_obj.get("done_time")
        if done_time:
            result.done_time = datetime.fromisoformat(done_time).timestamp()
        last_do_time = json_obj.get("last_do_time")
        if last_do_time:
            result.last_do_time = datetime.fromisoformat(last_do_time).timestamp()
        last_plan_time = json_obj.get("last_plan_time")
        if last_plan_time:
            result.last_plan_time = datetime.fromisoformat(last_plan_time).timestamp()
        last_check_time = json_obj.get("last_check_time")
        if last_check_time:
            result.last_check_time = datetime.fromisoformat(last_check_time).timestamp()  

        if result.task_id is None or result.title is None or result.create_time is None or result.create_time is None:
            logger.error(f"invalid task {json_obj}")
            return None

        return result
    @classmethod
    def create_by_dict(cls,json_obj:dict) -> 'AgentTask':
        creator = json_obj.get("creator")
        if creator is None:
            logger.error(f"invalid create task, creator is None")
            return None
        
        result = AgentTask()
        
        result.title = json_obj.get("title")
        result.detail = json_obj.get("detail")
        if result.detail is None:
            result.detail = result.title 
        result.priority = json_obj.get("priority")
        if result.priority is None:
            result.priority = 5

        result.tags = json_obj.get("tags")
        result.worker = json_obj.get("worker")
        result.createor = creator
        due_date = json_obj.get("due_date")
        if due_date:
            result.due_date = datetime.fromisoformat(due_date).timestamp()
        
        return result

class AgentWorkLog:
    def __init__(self) -> None:
        self.logid = "worklog#" + uuid.uuid4().hex
        self.owner_taskid:str = None
        self.owner_todoid:str = None
        self.type:str = "" # 默认为普通类型的log,特殊类型的Log一般伴随着重要的状态改变
        self.timestamp = time.time()
        self.content:str = None
        self.result:str = None
        self.meta : dict = None
        self.operator = None
        
    def to_dict(self) -> dict:
        pass

class AgentTaskManager(ABC):
    def __init__(self) -> None:
        pass
    
    @abstractmethod
    async def create_task(self,task:AgentTask,parent_id:str = None) -> str:
        pass

    @abstractmethod
    async def create_todos(self,owner_task_id:str,todos:List[AgentTodoTask]):
        # return todo_id
        pass

    @abstractmethod
    async def append_worklog(self,log:AgentWorkLog):
        pass

    @abstractmethod
    async def get_worklog(self,obj_id:str)->List[AgentWorkLog]:
        pass

    @abstractmethod   
    async def get_task(self,task_id:str) -> AgentTask:
        pass

    #@abstractmethod
    #async def get_task_by_fullpath(self,task_path:str) -> AgentTask:
    #    pass

    @abstractmethod   
    async def get_todo(self,todo_id:str) -> AgentTodoTask:
        pass

    @abstractmethod    
    async def get_sub_tasks(self,task_id:str) -> List[AgentTask]:
        pass

    @abstractmethod    
    async def get_sub_todos(self,task_id:str) -> List[AgentTodoTask]:
        pass

    #@abstractmethod    
    #async def get_task_depends(self,task_id:str) -> List[AgentTask]:
    #    pass

    @abstractmethod    
    async def list_task(self,filter:Optional[dict]) -> List[AgentTask]:
        pass

    @abstractmethod    
    async def update_task(self,task:AgentTask):
        pass

    @abstractmethod
    async def update_todo(self,todo:AgentTodoTask):
        pass

    #@abstractmethod    
    #async def update_task_state(self,task_id,state:str):
    #    pass
    
    #@abstractmethod    
    #async def update_todo_state(self,task_id,state:str):
    #    pass

    #subtask,todo共享其所在task的文件夹
    @abstractmethod    
    async def get_task_file(self,task_id:str,path:str)->str:
        #return fileid
        pass
    
    @abstractmethod
    async def set_task_file(self,task_id:str,path:str,fileid:str):
        pass

    @abstractmethod
    async def list_task_file(self,task_id:str,path:str):
        pass

    @abstractmethod
    async def remove_task_file(self,task_id:str,path:str):
        pass




