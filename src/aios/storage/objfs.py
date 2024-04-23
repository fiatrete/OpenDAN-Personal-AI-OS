from abc import ABC, abstractmethod
import sqlite3
from sqlite3 import Error
from typing import List

import threading
import time
import uuid
import logging

logger = logging.getLogger(__name__)

class ObjFSReader(ABC):
    @abstractmethod
    def get_obj_by_path(self,path):
        pass

    @abstractmethod
    def get_obj_by_id(self,obj_id):
        pass

    @abstractmethod
    def list_paths(self,base_path):
        pass


#ObjFS provides structured data storage similar to brain-like, as an object storage layer of Agent Friendly
class ObjFS(ObjFSReader):
    def __init__(self, db_file):
        """ initialize db connection """
        self.db_file = db_file
        self._get_conn()

    def _get_conn(self):
        """ get db connection """
        local = threading.local()
        if not hasattr(local, 'conn'):
            local.conn = self._create_connection(self.db_file)
        return local.conn

    def _create_connection(self, db_file):
        """ create a database connection to a SQLite database """
        conn = None
        try:
            conn = sqlite3.connect(db_file)

        except Error as e:
            logger.error("Error occurred while connecting to database: %s", e)
            return None

        if conn:
            self._create_table(conn)

        return conn
    
    def _create_table(self, conn):
        try:
            conn.execute('''CREATE TABLE IF NOT EXISTS objects
                        (id TEXT PRIMARY KEY, name TEXT, content TEXT, created_at REAL, modified_at REAL, size INTEGER)''')

            conn.execute('''CREATE TABLE IF NOT EXISTS paths
                        (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, obj_id TEXT, FOREIGN KEY(obj_id) REFERENCES objects(id))''')

        except Error as e:
            logger.error("Error occurred while creating tables: %s", e)

    def close(self):
        local = threading.local()
        if not hasattr(local, 'conn'):
            return
        local.conn.close()
        
    def add_obj(self,obj_uuid, name, content, paths) -> bool:
        conn = self._get_conn()
        c = conn.cursor()
        #obj id是guid,由外部生成

        # 获取当前时间戳
        current_time = time.time()

        # 计算内容大小
        content_size = len(content.encode('utf-8'))
        try:
            # 插入对象
            c.execute("INSERT INTO objects (id, name, content, created_at, modified_at, size) VALUES (?, ?, ?, ?, ?, ?)", (obj_uuid, name, content, current_time, current_time, content_size))

            # 插入路径
            for path in paths:
                c.execute("INSERT OR IGNORE INTO paths (path, obj_id) VALUES (?, ?)", (path, obj_uuid))

            conn.commit()
        except Error as e:
            logger.warning("Error occurred while adding object: %s", e)
            return False
        
        return True

    def update_obj(self,obj_id, new_content) -> bool:
        #UPDATE orders
        #SET data = json_set(
        #    data,
        #    '$.items[1].price',
        #    0.35
        #)
        #WHERE id = 1;
        
        try:
            conn = self._get_conn()
            c = conn.cursor()
            # 获取当前时间戳
            current_time = time.time()

            # 计算新内容大小

            new_content_size = len(new_content.encode('utf-8'))

            c.execute("UPDATE objects SET content = ?, modified_at = ?, size = ? WHERE id = ?", (new_content, current_time, new_content_size, obj_id))
            conn.commit()
            return True
        except Error as e:
            logger.warning("Error occurred while updating object: %s", e)
            return False

    def add_path(self,obj_id, new_path) -> bool:
        try:
            conn = self._get_conn()
            c = conn.cursor()        
            c.execute("INSERT OR IGNORE INTO paths (path, obj_id) VALUES (?, ?)", (new_path, obj_id))
            conn.commit()
            return True
        except Error as e:
            logger.warning("Error occurred while adding path: %s", e)
            return False

    def remove_path(self,path) -> bool:
        try:
            conn = self._get_conn()
            c = conn.cursor()    
            #TODO     
            c.execute("DELETE FROM paths WHERE path = ?", (path,))
            conn.commit()
            return True
        except Error as e:
            logger.warning("Error occurred while removing path: %s", e)
            return False

    def remove_obj(self,obj_id) -> bool:
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("DELETE FROM objects WHERE id = ?", (obj_id,))

            # 删除所有与该对象相关的路径
            c.execute("DELETE FROM paths WHERE obj_id = ?", (obj_id,))
            conn.commit()
            return True
        except Error as e:
            logger.warning("Error occurred while removing object: %s", e)
            return False

    def get_obj_by_path(self,path) -> str:
        try:
            conn = self._get_conn()
            c = conn.cursor()        
            c.execute("SELECT objects.id, objects.name, objects.content FROM objects JOIN paths ON objects.id = paths.obj_id WHERE paths.path = ?", (path,))
            obj_row = c.fetchone()
            if obj_row:
                return obj_row[2]
            return None
        except Error as e:
            logger.warning("Error occurred while getting object by path: %s", e)
            return None


    def get_obj_by_id(self,obj_id) -> str:
        try:
            conn = self._get_conn()
            c = conn.cursor()        
            c.execute("SELECT id, name, content FROM objects WHERE id = ?", (obj_id,))
            obj_row =  c.fetchone()
            if obj_row:
                return obj_row[2]
            return None
        except Error as e:
            logger.warning("Error occurred while getting object by id: %s", e)
            return None

    def list_paths(self,base_path)->List[str]:
        try:
            conn = self._get_conn()
            c = conn.cursor()        
            c.execute("SELECT path FROM paths WHERE path LIKE ? ESCAPE '/'", (base_path + "/%",))
            return [row[0] for row in c.fetchall()]
        except Error as e:
            logger.warning("Error occurred while listing paths: %s", e)
            return None
        
    def tree(self, base_path,max_depth=3):
        try:
            conn = self._get_conn()
            c = conn.cursor()        
            c.execute("SELECT path FROM paths WHERE path LIKE ? ESCAPE '/'", (base_path + "/%",))
            paths = [row[0] for row in c.fetchall()]
            tree = {}
            for path in paths:
                parts = path.split("/")
                node = tree
                for part in parts:
                    if part not in node:
                        node[part] = {}
                    node = node[part]
            return tree
        except Error as e:
            logger.warning("Error occurred while listing paths: %s", e)
            return None


