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

from .agent_base import AgentMsg,AgentTodo
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
        

    def set_root_path(self,path:str):
        self.root_path = path

    def get_prompt(self) -> AgentMsg:
        return None
    
    def get_role_prompt(self,role_id:str) -> AgentMsg:
        return None

    def get_knowledge_base(self) -> str:
        pass

    async def exec_op_list(self,oplist:List)->None:
        if oplist is None:
            return
        
        for op in oplist:
            if op["op"] == "create":
                return await self.create(op["path"],op["content"])
            elif op["op"] == "write":
                return await self.write(op["path"],op["content"],op["mode"])
            elif op["op"] == "delete":
                return await self.delete(op["path"])
            elif op["op"] == "rename":
                return await self.rename(op["path"],op["new_name"])
            elif op["op"] == "mkdir":
                return await self.mkdir(op["path"])
            elif op["op"] == "create_todo":
                todoObj = AgentTodo.from_dict(op["todo"])
                path = op.get("path")
                return await self.create_todo(path,todoObj)

            else:
                logger.error(f"execute op list failed: unknown op:{op['op']}")

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
    
    async def write(self,path:str,content:str,is_append:bool=False) -> str:
        file_path = self.root_path + path
        if is_append:
            async with aiofiles.open(file_path, mode='a', encoding="utf-8") as f:
                await f.write(content)
        else:
            async with aiofiles.open(file_path, mode='w', encoding="utf-8") as f:
                await f.write(content)
        return "success"

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
        
    async def delete(self,path:str) -> bool:
        file_path = self.root_path + path
        os.remove(file_path)
        return True
    
    async def mkdir(self,path:str) -> bool:
        dir_path = self.root_path + path
        os.makedirs(dir_path)
        return True
    
    async def rename(self,path:str,new_name:str) -> bool:
        file_path = self.root_path + path
        new_path = self.root_path + new_name
        os.rename(file_path,new_path)
        return True

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
            
            for entry in os.scandir(directory_path):
                is_dir = entry.is_dir()
                if not is_dir:
                    continue
                
                todo_count = todo_count +  1
                str_result = str_result + f"{'  '*(4-deep)}└─{entry.name}\n"
                await scan_dir(entry.path,deep-1)

        await scan_dir(directory_path,deep)
        return str_result,todo_count


    async def get_todo_by_path(self,path:str) -> AgentTodo:
        pass
    
    async def get_todo(self,id:str) -> AgentTodo:
        pass

    async def create_todo(self,path:str,todo:AgentTodo) -> None:
        if path is None:
            dir_path = f"/todos/{todo.title}"
        else:
            dir_path = f"/todos/{path}/{todo.title}"

        os.makedirs(self.root_path + dir_path)
        detail_path = f"{dir_path}/detail"
        await self.create(detail_path,json.dumps(todo.to_dict()))

    async def update_todo(self,path:str,todo:AgentTodo)->None:
        pass

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

