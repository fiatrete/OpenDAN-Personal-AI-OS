# pylint:disable=E0402
import sqlite3
import json
import threading
import logging
from datetime import datetime

from typing import Optional, List

logger = logging.getLogger(__name__)

class SimpleKnowledgeDB:
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
        tag_json = json.dumps(tag,ensure_ascii=False)  # 将标签转换为 JSON 字符串
        cursor.execute('''
            SELECT documents.doc_path
            FROM documents
            JOIN knowledge ON documents.doc_hash = knowledge.doc_hash
            WHERE json_extract(knowledge.tags, '$') LIKE ?
        ''', (tag))
        return [row[0] for row in cursor.fetchall()]
    
    def query(self,sql:str):
        pass
        #cursor = self.conn.cursor()
