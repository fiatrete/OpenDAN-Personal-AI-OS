# this env is designed for workflow owner filesystem, support file/directory operations

import json
import subprocess
import logging
import tempfile
import threading
import traceback
import time
import ast
import sys
import os
import re
import asyncio
import aiofiles
from typing import Any,List
import os
import chardet

from .agent_base import AgentMsg,AgentTodo,AgentPrompt,AgentTodoResult
from .environment import Environment,EnvironmentEvent
from .ai_function import AIFunction,SimpleAIFunction
from .storage import AIStorage,ResourceLocation

logger = logging.getLogger(__name__)

class WorkspaceEnvironment(Environment):
    def __init__(self, env_id: str) -> None:
        super().__init__(env_id)
        myai_path = AIStorage.get_instance().get_myai_dir() 
        self.root_path = f"{myai_path}/workspace/{env_id}"
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path+"/todos")

        self.known_todo = {}
        

    def set_root_path(self,path:str):
        self.root_path = path

    def get_prompt(self) -> AgentMsg:
        return None
    
    def get_role_prompt(self,role_id:str) -> AgentPrompt:
        return None

    def get_knowledge_base(self) -> str:
        pass

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
            if op["op"] == "create":
                await self.create(op["path"],op["content"])
            elif op["op"] == "write_file":
                is_append = op.get("is_append")
                if is_append is None:
                    is_append = False
                error_str = await self.write(op["path"],op["content"],is_append)
            elif op["op"] == "delete":
                error_str = await self.delete(op["path"])
            elif op["op"] == "rename":
                error_str = await self.rename(op["path"],op["new_name"])
            elif op["op"] == "mkdir":
                error_str = await self.mkdir(op["path"])
            elif op["op"] == "create_todo":
                todoObj = AgentTodo.from_dict(op["todo"])
                todoObj.worker = agent_id
                todoObj.createor = agent_id
                parent_id = op.get("parent")
                error_str = await self.create_todo(parent_id,todoObj)
            elif op["op"] == "update_todo":
                todo_id = op["id"]
                new_stat = op["state"]
                error_str = await self.update_todo(todo_id,new_stat)
            else:
                logger.error(f"execute op list failed: unknown op:{op['op']}")
                error_str = f"execute op list failed: unknown op:{op['op']}"
            
            if error_str:
                have_error = True
                result_str.append(error_str)
            else:
                result_str.append(f"execute success!")  
    
        
        return result_str,have_error

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

    async def read(self,path:str) -> str:
        file_path = self.root_path + path
        cur_encode = "utf-8"
        async with aiofiles.open(file_path,'rb') as f:
            cur_encode = chardet.detect(await f.read())['encoding']

        async with aiofiles.open(file_path, mode='r', encoding=cur_encode) as f:
            content = await f.read(2048)
        return content
    
    # use diff to update large file content
    async def write_diff(self,path:str,diff):
        pass 

    async def write(self,path:str,content:str,is_append:bool=False) -> str:
        file_path = self.root_path + path
        try:
            if is_append:
                async with aiofiles.open(file_path, mode='a', encoding="utf-8") as f:
                    await f.write(content)
            else:
                async with aiofiles.open(file_path, mode='w', encoding="utf-8") as f:
                    await f.write(content)
        except Exception as e:
            return str(e)
        return None

    async def create(self,path:str,content:str=None) -> bool:
        if content is None:
            # create dir
            dir_path = self.root_path + path
            os.makedirs(dir_path)
            return True
        else:
            file_path = self.root_path + path
            async with aiofiles.open(file_path, mode='w', encoding="utf-8") as f:
                await f.write(content)
            return True
        
    async def delete(self,path:str) -> str:
        try:
            file_path = self.root_path + path
            os.remove(file_path)
        except Exception as e:
            return str(e)
        
        return None
    
    async def mkdir(self,path:str) -> bool:
        dir_path = self.root_path + path
        os.makedirs(dir_path)
        return True
    
    async def rename(self,path:str,new_name:str) -> str:
        try:
            file_path = self.root_path + path
            new_path = self.root_path + new_name
            os.rename(file_path,new_path)
        except Exception as e:
            return str(e)
        
        return None

    async def get_todo_tree(self,path:str = None,deep:int = 4):
        if path:
            directory_path = self.root_path + "/todos/" + path
        else:
            directory_path = self.root_path + "/todos"

        
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
            directory_path = self.root_path + "/todos/" + path
        else:
            directory_path = self.root_path + "/todos"

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
                    relative_path = os.path.relpath(path, self.root_path + "/todos/")
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

            dir_path = f"{self.root_path}/todos/{todo_path}"
    
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
                detail_path =  f"{self.root_path}/todos/{todo.todo_path}/detail"
                async with aiofiles.open(detail_path, mode='w', encoding="utf-8") as f:
                    await f.write(json.dumps(todo.to_dict()))
                    return None
            else:
                return "todo not found."
        except Exception as e:
            return str(e)
    
    async def append_worklog(self,todo:AgentTodo,result:AgentTodoResult):
        worklog = f"{self.root_path}/todos/{todo.todo_path}/.worklog"

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

class CodeInterpreter:
    def __init__(self, language, debug_mode):
        self.language = language
        self.proc = None
        self.active_line = None
        self.debug_mode = debug_mode

    def start_process(self):
        start_cmd = sys.executable + " -i -q -u"
        self.proc = subprocess.Popen(start_cmd.split(),
                                        stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        text=True,
                                        bufsize=0)

        # Start watching ^ its `stdout` and `stderr` streams
        threading.Thread(target=self.save_and_display_stream,
                            args=(self.proc.stdout, False), # Passes False to is_error_stream
                            daemon=True).start()
        threading.Thread(target=self.save_and_display_stream,
                            args=(self.proc.stderr, True), # Passes True to is_error_stream
                            daemon=True).start()

    def warp_code(self,pycode:str)->str:
        # Add import traceback
        code = "import traceback\n" + pycode
        # Parse the input code into an AST
        parsed_code = ast.parse(code)
        # Wrap the entire code's AST in a single try-except block
        try_except = ast.Try(
            body=parsed_code.body,
            handlers=[
                ast.ExceptHandler(
                    type=ast.Name(id="Exception", ctx=ast.Load()),
                    name=None,
                    body=[
                        ast.Expr(
                            value=ast.Call(
                                func=ast.Attribute(value=ast.Name(id="traceback", ctx=ast.Load()), attr="print_exc", ctx=ast.Load()),
                                args=[],
                                keywords=[]
                            )
                        ),
                    ]
                )
            ],
            orelse=[],
            finalbody=[]
        )

        parsed_code.body = [try_except]
        return ast.unparse(parsed_code)
        
    def run(self,py_code:str):
        """
        Executes code.
        """
        # Get code to execute
        self.code = py_code 

        # Start the subprocess if it hasn't been started
        if not self.proc:
            try:
                self.start_process()
            except Exception as e:
                # Sometimes start_process will fail!
                # Like if they don't have `node` installed or something.
                
                traceback_string = traceback.format_exc()
                self.output = traceback_string
                # Before you return, wait for the display to catch up?
                # (I'm not sure why this works)
                time.sleep(0.1)
        
                return self.output

        self.output = ""

        self.print_cmd = 'print("{}")'
        code = self.warp_code(py_code)

        if self.debug_mode:
            print("Running code:")
            print(code)
            print("---")

        self.done = threading.Event()
        self.done.clear()

        # Write code to stdin of the process
        try:
            self.proc.stdin.write(code + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            return
        self.done.wait()
        time.sleep(0.1)
        return self.output

    def save_and_display_stream(self, stream, is_error_stream):

        for line in iter(stream.readline, ''):
            if self.debug_mode:
                print("Recieved output line:")
                print(line)
                print("---")
            
            line = line.strip()
            if is_error_stream and "KeyboardInterrupt" in line:
                raise KeyboardInterrupt
            elif "END_OF_EXECUTION" in line:
                self.done.set()
                self.active_line = None
            else:
                self.output += "\n" + line
                self.output = self.output.strip()


  
class ShellEnvironment(Environment):
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

    async def run_code(self,pycode:str) -> str:
        interpreter = CodeInterpreter("python",True)
        return interpreter.run(pycode)
    

# merge to standard workspace env, **ABANDON this!**
class KnowledgeBaseFileSystemEnvironment(Environment):
    def __init__(self, env_id: str) -> None:
        super().__init__(env_id)
        self.root_path = "."

        operator_param = {
            "path": "full path of target directory",
        }
        self.add_ai_function(SimpleAIFunction("list",
                                        "list the files and sub directory in target directory,result is a json array",
                                        self.list,operator_param))
        
        operator_param = {
            "path": "full path of target file",
        }
        self.add_ai_function(SimpleAIFunction("cat",
                                        "cat the file content in target path,result is a string",
                                        self.cat,operator_param))
    
    def set_root_path(self,path:str):
        self.root_path = path

    
    async def list(self,path:str) -> str:
        directory_path = self.root_path + path
        items = []

        with await aiofiles.os.scandir(directory_path) as entries:
            async for entry in entries:
                item_type = "directory" if entry.is_dir() else "file"
                items.append({"name": entry.name, "type": item_type})

        return json.dumps(items)

    async def cat(self,path:str) -> str:
        file_path = self.root_path + path
        cur_encode = "utf-8"
        async with aiofiles.open(file_path,'rb') as f:
            cur_encode = chardet.detect(await f.read())['encoding']

        async with aiofiles.open(file_path, mode='r', encoding=cur_encode) as f:
            content = await f.read(2048)
        return content

