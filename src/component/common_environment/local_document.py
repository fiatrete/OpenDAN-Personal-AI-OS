import os
import aiofiles
import chardet
import string
import sqlite3
import json
import re
import threading
import logging
import hashlib
from markdown import Markdown
import PyPDF2
import datetime
from typing import Optional, List
from aios import *
from aios.environment.workspace_env import TodoListEnvironment, TodoListType
from .local_file_system import FilesystemEnvironment

logger = logging.getLogger(__name__)

class MetaDatabase:
    def __init__(self,db_path:str):
        self.db_path = db_path
        self._get_conn()

    def _get_conn(self):
        """ get db connection """
        local = threading.local()
        if not hasattr(local, 'conn'):
            local.conn = self._create_connection(self.db_path)
        return local.conn


    def _create_connection(self, db_file):
        """ create a database connection to a SQLite database """
        conn = None
        try:
            conn = sqlite3.connect(db_file)
        except Exception as e:
            logger.error("Error occurred while connecting to database: %s", e)
            return None

        if conn:
            self._create_tables(conn)

        return conn

    def _create_tables(self,conn):
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                doc_path TEXT PRIMARY KEY,
                length INTEGER,
                last_modify TEXT,
                doc_hash TEXT,
                create_time TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge (
                doc_hash TEXT PRIMARY KEY,
                title TEXT,
                summary TEXT,
                content TEXT,
                catalogs TEXT,
                tags TEXT,
                llm_title TEXT,
                llm_summary TEXT,
                create_time TEXT
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_documents_doc_hash
            ON documents (doc_hash)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_knowledge_tags
            ON knowledge (tags)
        ''')

        conn.commit()

    def add_doc(self, doc_path: str, length: int, last_modify: str, doc_hash: Optional[str] = None):
        conn = self._get_conn()
        cursor = conn.cursor()
        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('''
            INSERT INTO documents (doc_path, length, last_modify, doc_hash,create_time) 
            VALUES (?, ?, ?, ?,?)
        ''', (doc_path, length, last_modify, doc_hash,create_time))
        conn.commit()

    def is_doc_exist(self, doc_path: str) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT doc_path
            FROM documents
            WHERE doc_path = ?
        ''', (doc_path,))
        return len(cursor.fetchall()) > 0

    def set_doc_hash(self, doc_path: str, doc_hash: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE documents
            SET doc_hash = ?
            WHERE doc_path = ?
        ''', (doc_hash, doc_path))
        conn.commit()

    def get_docs_without_hash(self,limit:int=1024) -> List[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT doc_path
            FROM documents
            WHERE doc_hash IS NULL OR doc_hash = ''
            ORDER BY create_time DESC
            LIMIT ?
        ''',(limit,))
        return [row[0] for row in cursor.fetchall()]

    #metadata["summary"]
    #metadata["catalogs"]
    #metadata["tags"]
    def add_knowledge(self, doc_hash: str, metadata: dict,content:str = None,):
        conn = self._get_conn()
        cursor = conn.cursor()

        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = metadata.get("summary", "")
        catalogs = json.dumps(metadata.get("catalogs", {}),ensure_ascii=False)
        title = metadata.get("title","")
        tags = ','.join(metadata.get("tags", []))

        cursor.execute('''
            INSERT INTO knowledge (doc_hash, title , summary , catalogs , tags,create_time) 
            VALUES (?, ?, ?, ?, ?,?)
        ''', (doc_hash, title, summary, catalogs, tags,create_time))
        conn.commit()

    #llm_result["summary"]
    #llm_result["tags"]
    #llm_result["catalog"]
    def set_knowledge_llm_result(self, doc_hash: str, meta: dict):
        conn = self._get_conn()
        cursor = conn.cursor()

        title = meta.get("title", "")
        summary = meta.get("summary", "")
        catalogs = json.dumps(meta.get("catalogs", {}),ensure_ascii=False)
        tags = ','.join(meta.get("tags", []))

        cursor.execute('''
            UPDATE knowledge
            SET llm_title = ?,llm_summary = ?, catalogs = ?, tags = ?
            WHERE doc_hash = ?
        ''', (title,summary, catalogs, tags, doc_hash))
        conn.commit()


    def get_hash_by_doc_path(self, doc_path: str) -> Optional[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT doc_hash
            FROM documents
            WHERE doc_path = ?
        ''', (doc_path,))
        row = cursor.fetchone()
        if row is None:
            return None
        return row[0]

    def get_knowledge(self, doc_hash: str) -> Optional[dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT title, summary, catalogs, tags, llm_title, llm_summary
            FROM knowledge
            WHERE doc_hash = ?
        ''', (doc_hash,))
        row = cursor.fetchone()
        if row is None:
            return None

        # get doc path
        cursor.execute('''
            SELECT doc_path
            FROM documents
            WHERE doc_hash = ?
        ''', (doc_hash,))
        row2 = cursor.fetchone()
        if row2 is None:
            return None
        doc_path = row2[0]


        return {
            "full_path": doc_path,
            "title": row[0],
            "summary": row[1],
            "catalogs": row[2],
            "tags": row[3],
            "llm_title" : row[4],
            "llm_summary" : row[5],
        }

    def get_knowledge_without_llm_title(self,limit:int=16) -> List[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT doc_hash
            FROM knowledge
            WHERE llm_title IS NULL OR llm_title = ''
            ORDER BY create_time DESC
            LIMIT ?
        ''',(limit,))
        return [row[0] for row in cursor.fetchall()]

    def query_docs_by_tag(self, tag: str) -> List[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        tag_json = json.dumps(tag,ensure_ascii=False)  # 将标签转换为 JSON 字符串
        cursor.execute('''
            SELECT documents.doc_path
            FROM documents
            JOIN knowledge ON documents.doc_hash = knowledge.doc_hash
            WHERE json_extract(knowledge.tags, '$') LIKE ?
        ''', (tag))
        return [row[0] for row in cursor.fetchall()]

# singleton
class LearningCache:
    _instance_lock = threading.Lock()
    _instance = None

    def __instance_init__(self):
        self.cache = {}
        self.cache_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with LearningCache._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.__instance_init__()
        return cls._instance

    def add(self, key, value):
        with self.cache_lock:
            self.cache[key] = value

    def get(self, key):
        with self.cache_lock:
            return self.cache.get(key)

    def remove(self, key):
        with self.cache_lock:
            return self.cache.pop(key, None)


class LocalKnowledgeBase(CompositeEnvironment):
    def __init__(self, workspace: str) -> None:
        super().__init__(workspace)
        self.root_path = f"{workspace}/knowledge"
        if os.path.exists(self.root_path) is False:
            os.makedirs(self.root_path)
        self.meta_db = MetaDatabase(f"{self.root_path}/kb.db")
        self.learning_cache = LearningCache()

        async def learn(op:dict):
            full_path = op.get("original_path")
            if not full_path:
                return
            meta = self.learning_cache.get(full_path)
            meta.update(op)

        self.add_ai_operation(SimpleAIAction(
            op="learn",
            description="update knowledge llm summary",
            func_handler=learn,
        ))

        self.fs = FilesystemEnvironment(self.root_path)
        self.add_env(self.fs)

    async def get_knowledege_catalog(self,path:str=None,only_dir =True,max_depth:int=5)->str:
        if path:
            full_path = f"{self.root_path}/{path}"
        else:
            full_path = self.root_path

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
    async def get_knowledge_meta(self,path:str) -> str:
        full_path = f"{self.root_path}/{path}"
        if os.islink(full_path):
            org_path = os.readlink(full_path)
            hash = self.meta_db.get_hash_by_doc_path(org_path)
            if hash:
                return self.meta_db.get_knowledge(org_path)

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


class ScanLocalDocument:
    def __init__(self, env: KnowledgePipelineEnvironment, config):
        self.env = env
        workspace = string.Template(config["workspace"]).substitute(myai_dir=AIStorage.get_instance().get_myai_dir())
        path = string.Template(config["path"]).substitute(myai_dir=AIStorage.get_instance().get_myai_dir())
        self.knowledge_base = LocalKnowledgeBase(workspace)
        self.path = path

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

    async def next(self):
        while True:
            for root, dirs, files in os.walk(self.path):
                for file in files:
                    if self._support_file(file):
                        full_path = os.path.join(root, file)
                        full_path = os.path.normpath(full_path)
                        if self.knowledge_base.meta_db.is_doc_exist(full_path):
                            continue
                        yield(full_path, full_path)
                    else:
                        continue
            yield(None, None)



class ParseLocalDocument:
    def __init__(self, env: KnowledgePipelineEnvironment, config: dict):
        self.env = env
        workspace = string.Template(config["workspace"]).substitute(myai_dir=AIStorage.get_instance().get_myai_dir())
        self.todo_list = TodoListEnvironment(workspace, TodoListType.TO_LEARN)
        self.knowledge_base = LocalKnowledgeBase(workspace)
        self.token_limit = config.get("token_limit", 4000)
        self.assign_to = config.get("assign_to")


    async def parse(self, full_path: str) -> str:
        file_stat = os.stat(full_path)
        if file_stat.st_size < 1:
            return full_path
        hash, parse_meta = self._parse_document(full_path)
        parse_meta["original_path"] = full_path
        llm_meta = await self._learn_by_agent(parse_meta)
        self.knowledge_base.meta_db.add_doc(full_path,file_stat.st_size,file_stat.st_mtime,hash)
        self.knowledge_base.meta_db.add_knowledge(hash,parse_meta)
        self.knowledge_base.meta_db.set_knowledge_llm_result(hash,llm_meta)
        path_list = llm_meta.get("path")
        new_title = llm_meta.get("title")
        if path_list:
            for new_path in path_list:
                new_path = f"{new_path}/{new_title}"
                await self.knowledge_base.fs.symlink(full_path, new_path)
                logger.info(f"create soft link {full_path} -> {new_path}")
        return full_path

    async def _get_meta_prompt(self,meta: dict,temp_meta = None,need_catalogs = False) -> str:
        kb_tree = await self.knowledge_base.get_knowledege_catalog()

        known_obj = {}
        title  = meta.get("title")
        if title:
            known_obj["title"] = title
        summary = meta.get("summary")
        if summary:
            known_obj["summary"] = summary
        tags = meta.get("tags")
        if tags:
            known_obj["tags"] = tags
        if need_catalogs:
            catalogs = meta.get("catalogs")
            if catalogs:
                known_obj["catalogs"] = catalogs

        if temp_meta:
            for key in temp_meta.keys():
                known_obj[key] = temp_meta[key]

        org_path = meta.get("original_path")
        known_obj["original_path"] = org_path
        return f"# Known information:\n## Current directory structure:\n{kb_tree}\n## Knowlege Metadata:\n{json.dumps(known_obj,ensure_ascii=False)}\n"

    def _token_len(self, text: str) -> int:
        return CustomAIAgent("", "gpt-4-turbo-preview", self.token_limit).token_len(text=text)


    async def _learn_by_agent(self, meta:dict) -> dict:
        # Objectives:
        #   Obtain better titles, abstracts, table of contents (if necessary), tags
        #   Determine the appropriate place to put it (in line with the organization's goals)
        # Known information:
        #   The reason why the target service's learn_prompt is being sorted
        #   Summary of the organization's work (if any)
        #   The current structure of the knowledge base (note the size control) gen_kb_tree_prompt (when empty, LLM should generate an appropriate initial directory structure)
        #   Original path, current title, abstract, table of contents

        # Sorting long files (general tricks)
        #   Indicate that the input is part of the content, let LLM generate intermediate results for the task
        #   Enter the content in sequence, when the last content block is input, LLM gets the result
        full_content = await self.knowledge_base.load_knowledge_content(meta["original_path"])
        full_content_len = self._token_len(full_content)
        full_path = meta["original_path"]
        self.knowledge_base.learning_cache.add(full_path, meta)


        if full_content_len < self.token_limit:
            # 短文章不用总结catalog
            todo = AgentTodo()
            todo.worker = self.assign_to
            todo.title = meta["title"]
            meta_prompt = await self._get_meta_prompt(meta,None)
            todo.detail = meta_prompt + full_content
            await self.todo_list.create_todo(None, todo)
            await self.todo_list.wait_todo_done(todo.todo_id)
        else:
            logger.warning(f"llm_read_article: article {full_path} use LLM loop learn!")
            pos = 0
            read_len = int(self.token_limit * 1.2)

            is_final = False
            while pos < full_content_len:
                _content = full_content[pos:pos+read_len]
                part_cotent_len = len(_content)
                if part_cotent_len < read_len:
                    # last chunk
                    is_final = True
                    part_content = f"<<Final Part:start at {pos}>>\n{_content}"
                else:
                    part_content = f"<<Part:start at {pos}>>\n{_content}"

                pos = pos + read_len
                temp_meta = self.knowledge_base.learning_cache.get(full_path)
                todo = AgentTodo()
                todo.worker = self.assign_to
                todo.title = meta["title"]
                meta_prompt = await self._get_meta_prompt(meta,temp_meta)
                todo.detail = meta_prompt + part_content
                self.todo_list.create_todo(None, todo)
                todo = await self.todo_list.wait_todo_done(todo.todo_id)
                if is_final:
                    break
        return self.knowledge_base.learning_cache.remove(full_path)

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
                    metadata["catalogs"] = json.dumps(catalogs,ensure_ascii=False)
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
            # traceback.print_exc()

        if not "title" in meta_data:
            meta_data["title"] = title
        logger.info("parse document %s!",doc_path)
        return hash_result, meta_data

