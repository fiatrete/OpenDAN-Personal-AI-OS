# pylint:disable=E0402
from datetime import datetime,timedelta
import json
import threading
from typing import Dict, List
import sqlite3

from ..frame.compute_kernel import ComputeKernel
from ..proto.ai_function import SimpleAIAction
from ..proto.agent_msg import AgentMsg, AgentMsgType
from ..proto.agent_task import AgentWorkLog

from .llm_context import GlobaToolsLibrary
from .chatsession import AIChatSession

import logging

logger = logging.getLogger(__name__)

class AgentMemory:
    def __init__(self,agent_id:str,db_path:str) -> None:
        self.agent_id:str= agent_id
        self.memory_db:str = db_path
        self.model_name:str = "gp4-1106-preview"
        self.threshold_hours = 72


    def _get_conn(self):
        """ get db connection """
        local = threading.local()
        if not hasattr(local, 'conn'):
            local.conn = self._create_connection(self.memory_db)
        return local.conn
    
    def _create_connection(self, db_file):
        """ create a database connection to a SQLite database """
        conn = None
        try:
            conn = sqlite3.connect(db_file)
        except Error as e:
            logging.error("Error occurred while connecting to database: %s", e)
            return None

        if conn:
            self._create_table(conn)

        return conn
    
    def get_session_from_msg(self,msg:AgentMsg) -> AIChatSession:
        if msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
            session_topic = msg.target + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.memory_db)
        else:
            session_topic = msg.get_sender() + "#" + msg.topic
            chatsession = AIChatSession.get_session(self.agent_id,session_topic,self.memory_db)
        return chatsession

    async def load_chatlogs(self,msg:AgentMsg,n:int=6,m:int=64,token_limit=800)->str:
        chatsession = self.get_session_from_msg(msg)
        # Must load n (n> = 2), and hope to load the M
        # The information in the # M is gradually added, knowing that it is less than 72 hours from the current time, and consumes enough tokens

        messages_n = chatsession.read_history(n) # read
        if len(messages_n) >= n:
            messages_m = chatsession.read_history(m,n)
        else:
            messages_m = []

        histroy_str = ""
        read_count = 0
        for msg in messages_n:
            dt = datetime.fromtimestamp(float(msg.create_time))
            formatted_time = dt.strftime('%y-%m-%d %H:%M:%S')
            record_str = f"{msg.sender},[{formatted_time}]\n{msg.body}\n"
            token_limit -= ComputeKernel.llm_num_tokens_from_text(record_str,self.model_name)
            if token_limit <= 32:
                break
            read_count += 1
            histroy_str = record_str + histroy_str

        if len(messages_n) > 2:
            if read_count < 3:
                logging.warning(f"read history {read_count} < 3, will not load more")

        now = datetime.now()
        for msg in messages_m:
            dt = datetime.fromtimestamp(float(msg.create_time))
            time_diff = now - dt
            if time_diff > timedelta(hours=self.threshold_hours):
                break

            formatted_time = dt.strftime('%y-%m-%d %H:%M:%S')
            record_str = f"{msg.sender},[{formatted_time}]\n{msg.body}\n"
            token_limit -= ComputeKernel.llm_num_tokens_from_text(record_str,self.model_name)
            if token_limit <= 32:
                break
            read_count += 1
            histroy_str = record_str + histroy_str

        return histroy_str 
    
    # async def action_chatlog_append(self,params:Dict) -> str:
    #    
    #     input_msg:AgentMsg = params.get("input").get("msg")
    #     llm_result = params.get("llm_result")
    #     chatsession = self.get_session_from_msg(input_msg)
    #     resp_msg = params.get("resp_msg")
    #     if resp_msg:
    #         tags =  llm_result.raw_result.get("tags")
    #         chatsession.append(input_msg,tags)
    #         chatsession.append(resp_msg,tags)
    
    #     return "OK"

    async def load_worklogs(self,operator_id:str,owner_id:str=None, work_types:List[str]=None,token_limit=800):
        conn = self._get_conn()
        c = conn.cursor()
        
        query = 'SELECT * FROM worklog WHERE 1=1'  
        params = []

        if operator_id is not None:
            query += ' AND operator=?'
            params.append(operator_id)

        if owner_id is not None:
            query += ' AND owner_id=?'
            params.append(owner_id)

        if work_types:
            query += ' AND work_type IN ({})'.format(', '.join('?'*len(work_types)))
            params.extend(work_types)
        
        query += ' ORDER BY timestamp DESC LIMIT 8'

        c.execute(query, tuple(params))
        rows = c.fetchall()
        conn.close()

        return [self.from_db_row(row) for row in rows]

    def _create_table(self,conn):
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS worklog (
                logid TEXT PRIMARY KEY,
                owner_id TEXT,
                work_type TEXT,
                timestamp REAL,
                content TEXT,
                result TEXT,
                meta TEXT,  
                operator TEXT
            )
        ''')
        conn.commit()
        conn.close()

    @classmethod
    def from_db_row(self,row):
        log = AgentWorkLog()
        # 这里高度依赖表结构的顺序
        log.logid, log.owner_id, log.work_type, log.timestamp, log.content, log.result, meta_str, log.operator = row
        log.meta = json.loads(meta_str) if meta_str else None
        return log
    
    async def append_worklog(self,log:AgentWorkLog)->str:
        conn = self._get_conn()
        c = conn.cursor()
        # 将meta字典转换为JSON字符串
        meta_str = json.dumps(log.meta,ensure_ascii=False) if log.meta else None
        c.execute('''
            INSERT INTO worklog (logid, owner_id, work_type, timestamp, content, result, meta, operator)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (log.logid, log.owner_id, log.work_type, log.timestamp, log.content, log.result, meta_str, log.operator))
        conn.commit()
        conn.close()

    async def get_contact_summary(self,contact_id:str) -> str:
        if contact_id is None:
            return None
        
        if contact_id == "lzc":
            return "lzc is your master. Male, 40 years old, Mother tongue is Chinese, senior software engineer."
        return None
    
    async def update_contact_summary(self,contact_id:str,summary:str) -> str:
        return "OK"
    
    async def get_sth_summary(self,sth_id:str) -> str:
        return None
    
    async def update_sth_summary(self,sth_id:str,summary:str) -> str:
        return None
    
    

    
    
