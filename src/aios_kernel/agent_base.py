import abc
import copy
from abc import abstractmethod
from datetime import datetime, timedelta
import logging
from enum import Enum
import uuid
import time
import re
import shlex
import json
from typing import List

from .ai_function import FunctionItem, AIFunction
from .compute_task import ComputeTaskResult,ComputeTaskResultCode
from .environment import Environment


logger = logging.getLogger(__name__)

class AgentMsgType(Enum):
    TYPE_MSG = 0
    TYPE_GROUPMSG = 1
    TYPE_INTERNAL_CALL = 10
    TYPE_ACTION = 20
    TYPE_EVENT = 30
    TYPE_SYSTEM = 40


class AgentMsgStatus(Enum):
    RESPONSED = 0
    INIT = 1
    SENDING = 2
    PROCESSING = 3
    ERROR = 4
    RECVED = 5
    EXECUTED = 6

# msg is a msg / msg resp
# msg body可以有内容类型（MIME标签），text, image, voice, video, file,以及富文本(html)
# msg is a inner function call with result
# msg is a Action with result

# qutoe Msg
# forword msg
# reply msg

# 逻辑上的同一个Message在同一个session中看到的msgid相同
#       在不同的session中看到的msgid不同

class AgentMsg:
    def __init__(self,msg_type=AgentMsgType.TYPE_MSG) -> None:
        self.msg_id = "msg#" + uuid.uuid4().hex
        self.msg_type:AgentMsgType = msg_type

        self.prev_msg_id:str = None
        self.quote_msg_id:str = None
        self.rely_msg_id:str = None # if not none means this is a respone msg
        self.session_id:str = None

        #forword info


        self.create_time = 0
        self.done_time = 0
        self.topic:str = None # topic is use to find session, not store in db

        self.sender:str = None # obj_id.sub_objid@tunnel_id
        self.target:str = None
        self.mentions:[] = None #use in group chat only
        #self.title:str = None
        self.body:str = None
        self.body_mime:str = None #//default is "text/plain",encode is utf8

        #type is call / action
        self.func_name = None
        self.args = None
        self.result_str = None

        #type is event
        self.event_name = None
        self.event_args = None

        self.status = AgentMsgStatus.INIT
        self.inner_call_chain = []
        self.resp_msg = None

    @classmethod
    def from_json(cls,json_obj:dict) -> 'AgentMsg':
        msg = AgentMsg()

        return msg

    @classmethod
    def create_internal_call_msg(self,func_name:str,args:dict,prev_msg_id:str,caller:str):
        msg = AgentMsg(AgentMsgType.TYPE_INTERNAL_CALL)
        msg.create_time = time.time()
        msg.func_name = func_name
        msg.args = args
        msg.prev_msg_id = prev_msg_id
        msg.sender = caller
        return msg

    def create_action_msg(self,action_name:str,args:dict,caller:str):
        msg = AgentMsg(AgentMsgType.TYPE_ACTION)
        msg.create_time = time.time()
        msg.func_name = action_name
        msg.args = args
        msg.prev_msg_id = self.msg_id
        msg.topic  = self.topic
        msg.sender = caller
        return msg

    def create_error_resp(self,error_msg:str):
        resp_msg = AgentMsg(AgentMsgType.TYPE_SYSTEM)
        resp_msg.create_time = time.time()

        resp_msg.rely_msg_id = self.msg_id
        resp_msg.body = error_msg
        resp_msg.topic  = self.topic
        resp_msg.sender = self.target
        resp_msg.target = self.sender

        return resp_msg

    def create_resp_msg(self,resp_body):
        resp_msg = AgentMsg()
        resp_msg.create_time = time.time()

        resp_msg.rely_msg_id = self.msg_id
        resp_msg.sender = self.target
        resp_msg.target = self.sender
        resp_msg.body = resp_body
        resp_msg.topic = self.topic

        return resp_msg

    def create_group_resp_msg(self,sender_id,resp_body):
        resp_msg = AgentMsg(AgentMsgType.TYPE_GROUPMSG)
        resp_msg.create_time = time.time()

        resp_msg.rely_msg_id = self.msg_id
        resp_msg.target = self.target
        resp_msg.sender = sender_id
        resp_msg.body = resp_body
        resp_msg.topic = self.topic

        return resp_msg

    def set(self,sender:str,target:str,body:str,topic:str=None) -> None:
        self.sender = sender
        self.target = target
        self.body = body
        self.create_time = time.time()
        if topic:
            self.topic = topic

    def get_msg_id(self) -> str:
        return self.msg_id

    def get_sender(self) -> str:
        return self.sender

    def get_target(self) -> str:
        return self.target

    def get_prev_msg_id(self) -> str:
        return self.prev_msg_id

    def get_quote_msg_id(self) -> str:
        return self.quote_msg_id

    @classmethod
    def parse_function_call(cls,func_string:str):
        str_list = shlex.split(func_string)
        func_name = str_list[0]
        params = str_list[1:]
        return func_name, params

class AgentPrompt:
    def __init__(self,prompt_str = None) -> None:
        self.messages = []
        if prompt_str:
            self.messages.append({"role":"user","content":prompt_str})
        self.system_message = None

    def as_str(self)->str:
        result_str = ""
        if self.system_message:
            result_str += self.system_message.get("role") + ":" + self.system_message.get("content") + "\n"
        if self.messages:
            for msg in self.messages:
                result_str += msg.get("role") + ":" + msg.get("content") + "\n"

        return result_str

    def to_message_list(self):
        result = []
        if self.system_message:
            result.append(self.system_message)
        result.extend(self.messages)
        return result

    def append(self,prompt):
        if prompt is None:
            return

        if prompt.system_message is not None:
            if self.system_message is None:
                self.system_message = copy.deepcopy(prompt.system_message)
            else:
                self.system_message["content"] += prompt.system_message.get("content")

        self.messages.extend(prompt.messages)

    def get_prompt_token_len(self):
        result = 0

        if self.system_message:
            result += len(self.system_message.get("content"))
        for msg in self.messages:
            result += len(msg.get("content"))

        return result

    def load_from_config(self,config:list) -> bool:
        if isinstance(config,list) is not True:
            logger.error("prompt is not list!")
            return False
        self.messages = []
        for msg in config:
            if msg.get("content"):
                if msg.get("role") == "system":
                    self.system_message = msg
                else:
                    self.messages.append(msg)
            else:
                logger.error("prompt message has no content!")
        return True

class LLMResult:
    def __init__(self) -> None:
        self.state : str = "ignore"
        self.resp : str = ""
        self.raw_resp = None
        self.paragraphs : dict[str,FunctionItem] = []


        self.post_msgs : List[AgentMsg] = []
        self.send_msgs : List[AgentMsg] = []
        self.calls : List[FunctionItem] = []
        self.post_calls : List[FunctionItem] = []
        self.op_list : List[FunctionItem] = [] # op_list is a optimize design for saving token
    @classmethod
    def from_json_str(self,llm_json_str:str) -> 'LLMResult':
        r = LLMResult()
        if llm_json_str is None:
            r.state = "ignore"
            return r
        if llm_json_str == "ignore":
            r.state = "ignore"
            return r

        llm_json = json.loads(llm_json_str)
        r.state = llm_json.get("state")
        r.resp = llm_json.get("resp")
        r.raw_resp = llm_json

        post_msgs = llm_json.get("post_msg")
        r.post_msgs = []
        if post_msgs:
            for msg in post_msgs:
                new_msg = AgentMsg()
                target_id = msg.get("target")
                msg_content = msg.get("content")
                new_msg.set("",target_id,msg_content)
                r.post_msgs.append(new_msg)
                #new_msg.msg_type = AgentMsgType.TYPE_MSG

        r.calls = llm_json.get("calls")
        r.post_calls = llm_json.get("post_calls")
        r.op_list = llm_json.get("op_list")

        return r

    @classmethod
    def from_str(self,llm_result_str:str,valid_func:List[str]=None) -> 'LLMResult':
        r = LLMResult()

        if llm_result_str is None:
            r.state = "ignore"
            return r
        if llm_result_str == "ignore":
            r.state = "ignore"
            return r

        if llm_result_str[0] == "{":
            return LLMResult.from_json_str(llm_result_str)

        lines = llm_result_str.splitlines()
        is_need_wait = False

        def check_args(func_item:FunctionItem):
            match func_name:
                case "send_msg":# /send_msg $target_id
                    if len(func_args) != 1:
                        return False

                    new_msg = AgentMsg()
                    target_id = func_item.args[0]
                    msg_content = func_item.body
                    new_msg.set("",target_id,msg_content)

                    r.send_msgs.append(new_msg)
                    is_need_wait = True
                    return True

                case "post_msg":# /post_msg $target_id
                    if len(func_args) != 1:
                        return False

                    new_msg = AgentMsg()
                    target_id = func_item.args[0]
                    msg_content = func_item.body
                    new_msg.set("",target_id,msg_content)
                    r.post_msgs.append(new_msg)
                    return True

                case "call":# /call $func_name $args_str
                    r.calls.append(func_item)
                    is_need_wait = True
                    return True
                case "post_call": # /post_call $func_name,$args_str
                    r.post_calls.append(func_item)
                    return True
                case _:
                    if valid_func is not None:
                        if func_name in valid_func:
                            r.paragraphs[func_name] = func_item
                            return True

            return False


        current_func : FunctionItem = None
        for line in lines:
            if line.startswith("##/"):
                if current_func:
                    if check_args(current_func) is False:
                        r.resp += current_func.dumps()

                func_name,func_args = AgentMsg.parse_function_call(line[3:])
                current_func = FunctionItem(func_name,func_args)
            else:
                if current_func:
                    current_func.append_body(line + "\n")
                else:
                    r.resp += line + "\n"

        if current_func:
            if check_args(current_func) is False:
                r.resp += current_func.dumps()

        if len(r.send_msgs) > 0 or len(r.calls) > 0:
            r.state = "waiting"
        else:
            r.state = "reponsed"

        return r

class AgentReport:
    def __init__(self):
        pass

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


class AgentWorkLog:
    def __init__(self) -> None:
        pass


class BaseAIAgent(abc.ABC):
    @abstractmethod
    def get_id(self) -> str:
        pass

    @abstractmethod
    def get_llm_model_name(self) -> str:
        pass

    @abstractmethod
    def get_max_token_size(self) -> int:
        pass

    @classmethod
    def get_inner_functions(cls, env:Environment) -> (dict,int):
        if env is None:
            return None,0

        all_inner_function = env.get_all_ai_functions()
        if all_inner_function is None:
            return None,0

        result_func = []
        result_len = 0
        for inner_func in all_inner_function:
            func_name = inner_func.get_name()
            this_func = {}
            this_func["name"] = func_name
            this_func["description"] = inner_func.get_description()
            this_func["parameters"] = inner_func.get_parameters()
            result_len += len(json.dumps(this_func)) / 4
            result_func.append(this_func)

        return result_func,result_len

    async def do_llm_complection(
        self,
        prompt:AgentPrompt,
        org_msg:AgentMsg=None, 
        env:Environment=None,
        inner_functions=None,
        is_json_resp=False,
    ) -> ComputeTaskResult:
        from .compute_kernel import ComputeKernel
        #logger.debug(f"Agent {self.agent_id} do llm token static system:{system_prompt_len},function:{function_token_len},history:{history_token_len},input:{input_len}, totoal prompt:{system_prompt_len + function_token_len + history_token_len} ")
        if inner_functions is None and env is not None:
            inner_functions,_ = BaseAIAgent.get_inner_functions(env)
        if is_json_resp:
            task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,resp_mode="json",mode_name=self.get_llm_model_name(),max_token=self.get_max_token_size(),inner_functions=inner_functions,timeout=None)
        else:
            task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,resp_mode="text",mode_name=self.get_llm_model_name(),max_token=self.get_max_token_size(),inner_functions=inner_functions,timeout=None)
        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"_do_llm_complection llm compute error:{task_result.error_str}")
            #error_resp = msg.create_error_resp(task_result.error_str)
            return task_result

        result_message = task_result.result.get("message")
        inner_func_call_node = None
        if result_message:
            inner_func_call_node = result_message.get("function_call")

        if inner_func_call_node:
            call_prompt : AgentPrompt = copy.deepcopy(prompt)
            task_result = await self._execute_func(env,inner_func_call_node,call_prompt,inner_functions,org_msg)
            
        return task_result
     
    async def _execute_func(
        self, 
        env: Environment, 
        inner_func_call_node: dict,
        prompt: AgentPrompt, 
        inner_functions: dict, 
        org_msg:AgentMsg,
        stack_limit = 5
    ) -> ComputeTaskResult:
        from .compute_kernel import ComputeKernel
        func_name = inner_func_call_node.get("name")
        arguments = json.loads(inner_func_call_node.get("arguments"))
        logger.info(f"llm execute inner func:{func_name} ({json.dumps(arguments)})")

        func_node : AIFunction = env.get_ai_function(func_name)
        if func_node is None:
            result_str = f"execute {func_name} error,function not found"
        else:
            try:
                result_str:str = await func_node.execute(**arguments)
            except Exception as e:
                result_str = f"execute {func_name} error:{str(e)}"
                logger.error(f"llm execute inner func:{func_name} error:{e}")


        logger.info("llm execute inner func result:" + result_str)
        
        prompt.messages.append({"role":"function","content":result_str,"name":func_name})
        task_result:ComputeTaskResult = await ComputeKernel.get_instance().do_llm_completion(prompt,mode_name=self.get_llm_model_name(),max_token=self.get_max_token_size(),inner_functions=inner_functions)
        if task_result.result_code != ComputeTaskResultCode.OK:
            logger.error(f"llm compute error:{task_result.error_str}")
            return task_result
       
        if org_msg:
            internal_call_record = AgentMsg.create_internal_call_msg(func_name,arguments,org_msg.get_msg_id(),org_msg.target)
            internal_call_record.result_str = task_result.result_str
            internal_call_record.done_time = time.time()
            org_msg.inner_call_chain.append(internal_call_record)

        inner_func_call_node = None
        if stack_limit > 0:
            result_message : dict = task_result.result.get("message")
            if result_message:
                inner_func_call_node = result_message.get("function_call")

        if inner_func_call_node:
            return await self._execute_func(env,inner_func_call_node,prompt,inner_functions,org_msg,stack_limit-1)
        else:
            return task_result


class CustomAIAgent(BaseAIAgent):
    def __init__(self, agent_id: str, llm_model_name: str, max_token_size: int) -> None:
        self.agent_id = agent_id
        self.llm_model_name = llm_model_name
        self.max_token_size = max_token_size

    def get_id(self) -> str:
        return self.agent_id

    def get_llm_model_name(self) -> str:
        return self.llm_model_name

    def get_max_token_size(self) -> int:
        return self.max_token_size