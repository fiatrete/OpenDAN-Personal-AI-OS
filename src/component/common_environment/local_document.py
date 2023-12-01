# import os
# import aiofiles
# import chardet
# import logging
# import string
# from knowledge import ImageObjectBuilder, DocumentObjectBuilder, KnowledgePipelineEnvironment, KnowledgePipelineJournal
# from aios_kernel.storage import AIStorage


import os
import aiofiles
import chardet
import logging
import string
import sqlite3
import json
import threading
import logging
from datetime import datetime
from typing import Optional, List
from knowledge import ImageObjectBuilder, DocumentObjectBuilder, KnowledgePipelineEnvironment, KnowledgePipelineJournal
from aios_kernel import AIStorage, SimpleEnvironment


class ScanLocalDocument:
    def __init__(self, env: KnowledgePipelineEnvironment, config):
        self.env = env
        path = string.Template(config["path"]).substitute(myai_dir=AIStorage.get_instance().get_myai_dir())
        config["path"] = path
        self.config = config  

    def path(self):
        return self.config["path"]
        
    async def next(self):
        while True:
            journals = self.env.journal.latest_journals(1)
            from_time = 0
            if len(journals) == 1:
                latest_journal = journals[0]
                if latest_journal.is_finish():
                    yield None
                    continue
                from_time = os.path.getctime(latest_journal.get_input())
                if os.path.getmtime(self.path()) <= from_time:
                    yield (None, None)
                    continue
            
            file_pathes = sorted(os.listdir(self.path()), key=lambda x: os.path.getctime(os.path.join(self.path(), x)))
            for rel_path in file_pathes:
                file_path = os.path.join(self.path(), rel_path)
                timestamp = os.path.getctime(file_path)
                if timestamp <= from_time:
                    continue
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.pdf', '.md', '.txt']:
                    logging.info(f"knowledge dir source found document file {file_path}")
                    yield (file_path, file_path)
            yield (None, None)

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
        create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    #metadata["catelogs"]
    #metadata["tags"]
    def add_knowledge(self, doc_hash: str, title: str, metadata: dict,content:str = None,):
        conn = self._get_conn()
        cursor = conn.cursor()

        create_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = metadata.get("summary", "")
        catalogs = metadata.get("catalogs","")
        tags = ','.join(metadata.get("tags", []))

        cursor.execute('''
            INSERT INTO knowledge (doc_hash, title , summary , catalogs , tags,create_time) 
            VALUES (?, ?, ?, ?, ?,?)
        ''', (doc_hash, title, summary, catalogs, tags,create_time))
        conn.commit()

    #llm_result["summary"]
    #llm_result["tags"]
    #llm_result["catelog"]
    def set_knowledge_llm_result(self, doc_hash: str, llm_result: dict):
        conn = self._get_conn()
        cursor = conn.cursor()

        title = llm_result.get("title", "")
        summary = llm_result.get("summary", "")
        catalogs = json.dumps(llm_result.get("catalogs", {}))
        tags = ','.join(llm_result.get("tags", []))

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
        tag_json = json.dumps(tag)  # 将标签转换为 JSON 字符串
        cursor.execute('''
            SELECT documents.doc_path
            FROM documents
            JOIN knowledge ON documents.doc_hash = knowledge.doc_hash
            WHERE json_extract(knowledge.tags, '$') LIKE ?
        ''', (tag))
        return [row[0] for row in cursor.fetchall()]


class DocumentKnowledgeBase(SimpleEnvironment):
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


class ParseLocalDocument:
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
    
    async def parse(self, file_path: str) -> str:



#  async def get_knowledege_catalog(self,path:str=None,only_dir =True,max_depth:int=5)->str:
#         if path:
#             full_path = f"{self.root_path}/knowledge/{path}"
#         else:
#             full_path = f"{self.root_path}/knowledge"
        
#         catlogs,file_count = await self.get_directory_structure(full_path,max_depth,only_dir)
#         return catlogs
 
#     async def get_directory_structure(self,root_dir, max_depth:int=4, only_dir=True, indent=1):
#         file_count = 0
#         structure_str = ''
#         if os.path.isdir(root_dir):
#             sub_files = []
#             with os.scandir(root_dir) as it:
#                 for entry in it:
#                     if entry.is_dir():
#                         sub_structure, sub_count = await self.get_directory_structure(entry.path, max_depth, only_dir, indent + 1)
#                         if sub_structure:
#                             structure_str += sub_structure
#                         file_count += sub_count
#                     else:
#                         file_count += 1
#                         sub_files.append(entry.name)

#                 if only_dir is False:
#                     for file_name in sub_files:
#                         structure_str = structure_str + '  ' * (indent+1) + file_name + '\n' 

#             dir_name = os.path.basename(root_dir)
#             dir_info = f"{dir_name} <count: {file_count}>"
        

#             structure_str = '  ' * indent + dir_info + '\n' + structure_str

#         if indent - 1 >= max_depth:
#             return None, file_count
#         else:
#             return structure_str, file_count

#     # inner_function    
#     async def get_knowledge(self,path:str) -> str:
#         full_path = f"{self.root_path}/knowledge/{path}"
#         if os.islink(full_path):
#             org_path = os.readlink(full_path)
#             hash = self.kb_db.get_hash_by_doc_path(org_path)
#             if hash:
#                 return self.kb_db.get_knowledge(org_path)
        
#         return "not found"

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
        
    