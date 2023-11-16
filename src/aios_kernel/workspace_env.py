# this env is designed for workflow owner filesystem, support file/directory operations

import hashlib
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

from markdown import Markdown
import PyPDF2
from .agent_base import AgentMsg,AgentTodo,AgentPrompt,AgentTodoResult
from .environment import Environment,EnvironmentEvent
from .ai_function import AIFunction,SimpleAIFunction
from .storage import AIStorage,ResourceLocation
from .simple_kb_db import SimpleKnowledgeDB

logger = logging.getLogger(__name__)

class WorkspaceEnvironment(Environment):
    def __init__(self, env_id: str) -> None:
        super().__init__(env_id)
        myai_path = AIStorage.get_instance().get_myai_dir() 
        self.root_path = f"{myai_path}/workspace/{env_id}"
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path+"/todos")

        self.known_todo = {}
        self.kb_db = SimpleKnowledgeDB(f"{self.root_path}/kb.db")
        self.doc_dirs = {}
        self._scan_thread = None 
        self._scan_dirthread = None
        

    def set_root_path(self,path:str):
        self.root_path = path

    def get_prompt(self) -> AgentMsg:
        return None
    
    def get_role_prompt(self,role_id:str) -> AgentPrompt:
        return None

    def get_knowledge_base(self,root_dir=None,indent=0) -> str:
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
        
    # TODO use diff to update large file content
    async def update_by_diff(self,path:str,diff):

        pass 
    
    # doc system （read_only,agent cann't modify doc）

    # inner_function
    async def list_db(self) -> str:
        pass
    # inner_function
    async def get_db_desc(self,db_name:str) -> str:
        pass  
    # inner_function
    async def query(self,db_name:str,sql:str) -> str:
        pass

    # search (web)
    # inner_function
    async def google_search(self,keyword:str,opt=None) -> str:
        pass

    # inner_function
    async def local_search(self,keyword:str,root_path=None ,opt=None) -> str:
        pass
    
    # inner_function, might be return a image is better
    async def web_get(self,url:str) -> str:
        pass
    
    # inner_function
    async def blockchain_get(self,chainid:str,query:dict) -> str:
        pass

    # code interpreter
    # inner_function or operation
    async def eval_code(self,pycode:str) -> str:
        pass
    
    # operation or inner_function
    async def improve_code(self,path:str):
        pass
    
    # operation or inner_function
    async def run(self,file_path:str)->str:
        pass

    # operation or inner_function
    async def pub_service(self,project_path:str):
        pass

    # operation or inner_function
    async def exec_tx(self,chain_id:str,tx:dict) -> str:
        pass
    
    # social ability
    # operation or inner_function
    async def post_message(self,target:str,msg:AgentMsg,wait_time) -> AgentMsg:
        pass
    
    # operation or inner_function
    async def add_contact(self,name:str,contact_info) -> str:
        pass

    # inner_function , include contact realtime info
    async def get_contact(self,name_list:List[str],opt:dict) -> List:
        pass


    # Task/todo system , create,update,delete,query
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

    async def set_wakeup_timer(self,todo_id:str,timestamp:int) -> str:
        pass

    # knowledge base system
    def get_knowledge_base_ai_functions(self):
        all_inner_function = []

        all_inner_function.append(SimpleAIFunction("get_knowledge_catalog","get knowledge catalog in tree format",
                                                                self.get_knowledege_catalog,
                                                                {"path":f"catalog path,none is /","depth":"max depth of catalog tree,default is 4"}))
        all_inner_function.append(SimpleAIFunction("get_knowledge","get knowledge metadata",
                                                                self.get_knowledge,
                                                                {"path":f"knowledge path"}))
        all_inner_function.append(SimpleAIFunction("load_knowledge_content","load knowledge content",
                                                                 self.load_knowledge_content,
                                                                  {"path":f"knowledge path","pos":"start position of content","length":"length of content"}))
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

    async def get_knowledege_catalog(self,path:str=None,only_dir =True,max_depth:int=5)->str:
        if path:
            full_path = f"{self.root_path}/knowledge/{path}"
        else:
            full_path = f"{self.root_path}/knowledge"
        
        catlogs,file_count = await self.get_directory_structure(full_path,max_depth,only_dir)
        return catlogs
 
    async def get_directory_structure(self,root_dir, max_depth:int=4, only_dir=True, indent=1):
        file_count = 0
        structure_str = ''
        if os.path.isdir(root_dir):
            sub_files = []
            with os.scandir(root_dir) as it:
                for entry in it:
                    if entry.is_dir():
                        sub_structure, sub_count = await self.get_directory_structure(entry.path, max_depth, only_dir, indent + 1)
                        if sub_structure:
                            structure_str += sub_structure
                        file_count += sub_count
                    else:
                        file_count += 1
                        sub_files.append(entry.name)

                if only_dir is False:
                    for file_name in sub_files:
                        structure_str = structure_str + '  ' * (indent+1) + file_name + '\n' 

            dir_name = os.path.basename(root_dir)
            dir_info = f"{dir_name} <count: {file_count}>"
        

            structure_str = '  ' * indent + dir_info + '\n' + structure_str

        if indent - 1 >= max_depth:
            return None, file_count
        else:
            return structure_str, file_count

    # inner_function    
    async def get_knowledge(self,path:str) -> str:
        full_path = f"{self.root_path}/knowledge/{path}"
        if os.islink(full_path):
            org_path = os.readlink(full_path)
            hash = self.kb_db.get_hash_by_doc_path(org_path)
            if hash:
                return self.kb_db.get_knowledge(org_path)
        
        return "not found"

    async def load_knowledge_content(self,path:str,pos:int=0,length:int=None) -> str:
        if path.endswith("pdf"):
            logger.info("load_knowledge_content:pdf")
            dir_path = os.path.dirname(path)
            base_name = os.path.basename(path)
            text_content_path = f"{dir_path}/.{base_name}.txt"
            if os.path.exists(text_content_path) is False:
                return None
            async with aiofiles.open(path, mode='r', encoding=cur_encode) as f:
                await f.seek(pos)
                content = await f.read(length)
                return content
        else:
            async with aiofiles.open(path,'rb') as f:
                cur_encode = chardet.detect(await f.read())['encoding']

            async with aiofiles.open(path, mode='r', encoding=cur_encode) as f:
                await f.seek(pos)
                content = await f.read(length)
                return content

        return "load content failed."

    def _add_document_dir(self,path:str):
        self.doc_dirs[path] = 0

    def _start_scan_document(self):
        if self._scan_thread is None:
            self._scan_thread = threading.Thread(target=self._scan_document)
            self._scan_thread.start()
        if self._scan_dirthread is None:
            self._scan_dirthread = threading.Thread(target=self._scan_dir)
            self._scan_dirthread.start()

    def _parse_pdf_bookmarks(self,bookmarks, parent:list):

        for item in bookmarks:
            if isinstance(item,list):
                self._parse_pdf_bookmarks(item,parent)
            else:
                if item.title:
                    new_item = {}
                    new_item["page"] = item.page.idnum
                    new_item["title"] = item.title 
                    my_childs = []
                    if item.childs:
                        if len(item.childs) > 0:
                            self._parse_pdf_bookmarks(item.childs, my_childs)
                            new_item["childs"] = my_childs
                    parent.append(new_item)
                else:
                    logger.warning("parse pdf bookmarks failed: item.title is None!")

        return

    def _parse_pdf(self,doc_path:str):
        metadata = {}
        with open(doc_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            try:
                doc_info = reader.metadata
                if doc_info:
                    if doc_info.title:
                        metadata["title"] = doc_info.title
                    if doc_info.author:
                        metadata["authors"] = doc_info.author
            except Exception as e:
                logger.warn("parse pdf metadata failed:%s",e)

            dir_path = os.path.dirname(doc_path)
            base_name = os.path.basename(doc_path)
            text_content_path = f"{dir_path}/.{base_name}.txt"
            full_text = ""

            for page in reader.pages:
                text = page.extract_text()
                full_text += text
            with open(text_content_path, 'w', encoding='utf-8') as f:
                f.write(full_text)

            try:
                bookmarks = reader.outline
                if bookmarks:
                    catalogs = []
                    self._parse_pdf_bookmarks(bookmarks,catalogs)
                    metadata["catalogs"] = json.dumps(catalogs)
            except Exception as e:
                logger.warn("parse pdf bookmarks failed:%s",e)

        return metadata

    def _parse_txt(self,doc_path:str):
        return {}

    def _parse_md(self,doc_path:str):
        metadata = {} 
        cur_encode = "utf-8"
        with open(doc_path,'rb') as f:
            cur_encode = chardet.detect(f.read(1024))['encoding']

        with open(doc_path, mode='r', encoding=cur_encode) as f:
            content = f.read()
            match = re.search(r'^# (.*)', content, re.MULTILINE)
            if match:
                metadata['title'] = match.group(1).strip()
            md = Markdown(extensions=['toc'])
            html_str = md.convert(content)
            toc = md.toc
            if toc:
                metadata['catalogs'] = toc
            
        return metadata

    def _parse_document(self,doc_path:str):
        hash_result = None
        title = os.path.basename(doc_path)
        meta_data = {}

        with open(doc_path, "rb") as f:
            hash_md5 = hashlib.md5()
            for chunk in iter(lambda: f.read(1024*1024), b""):
                hash_md5.update(chunk)
            hash_result = hash_md5.hexdigest()
        try:
            if doc_path.endswith(".md"):
                meta_data = self._parse_md(doc_path)
            elif doc_path.endswith(".pdf"):
                meta_data = self._parse_pdf(doc_path)
        except Exception as e:
            logger.error("parse document %s failed:%s",doc_path,e)
            traceback.print_exc()

        if meta_data.get("title"):
            title = meta_data["title"]
        logger.info("parse document %s!",doc_path)
        return hash_result,title,meta_data


    def _support_file(self,file_name:str) -> bool:
        if file_name.startswith("."):
            return False
        
        if file_name.endswith(".pdf"):
            return True
        if file_name.endswith(".md"):
            return True
        if file_name.endswith(".txt"):
            return True
        return False

    def _scan_dir(self):
        while True:
            time.sleep(10)
            for directory in self.doc_dirs.keys():
                now = time.time()
                if now - self.doc_dirs[directory] > 60*15:
                    self.doc_dirs[directory] = time.time()
                else:
                    continue

                for root, dirs, files in os.walk(directory):
                    for file in files:
                        if self._support_file(file):
                            full_path = os.path.join(root, file)
                            full_path = os.path.normpath(full_path)
                            if self.kb_db.is_doc_exist(full_path):
                                continue
                            
                            file_stat = os.stat(full_path)
                            if file_stat.st_size < 1:
                                continue

                            if file_stat.st_size < 1024*1024*8:
                                #parse and insert
                                hash,title,meta_data = self._parse_document(full_path)
                                self.kb_db.add_doc(full_path,file_stat.st_size,file_stat.st_mtime,hash)
                                self.kb_db.add_knowledge(hash,title,meta_data)
                                
                            else:
                                self.kb_db.add_doc(full_path,file_stat.st_size,file_stat.st_mtime)

    def _scan_document(self):
       while True:
        time.sleep(10)
        parse_queue = self.kb_db.get_docs_without_hash()
        for doc_path in parse_queue:
                hash,title,meta_data = self._parse_document(doc_path)
                self.kb_db.set_doc_hash(doc_path,hash)
                self.kb_db.add_knowledge(hash,title,meta_data)
        
    


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

