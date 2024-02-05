# pylint:disable=E0402
from datetime import datetime,timedelta
import json
import os
import threading
from typing import Dict, List
import sqlite3

import aiofiles

from ..storage.storage import AIStorage
from ..frame.compute_kernel import ComputeKernel
from ..frame.contact_manager import ContactManager
from ..frame.contact import Contact
from ..proto.ai_function import ParameterDefine, SimpleAIAction, SimpleAIFunction
from ..proto.agent_msg import AgentMsg, AgentMsgType
from ..proto.agent_task import AgentWorkLog

from .llm_context import GlobaToolsLibrary
from .chatsession import AIChatSession

import logging

logger = logging.getLogger(__name__)


#class ObjectSummary:
#    def __init__(self) -> None:
#        self.summary : str = None
#        self.object_name : str = None
#        self.priority : int = 5
        # [info_source, info]
#        self.infos : Dict[str,str] = {}



class AgentMemory:
    def __init__(self,agent_id:str,base_dir:str) -> None:
        self.agent_memory_base_dir = base_dir
        self.agent_id:str= agent_id

        AIStorage.get_instance().ensure_directory_exists(self.agent_memory_base_dir)
        AIStorage.get_instance().ensure_directory_exists(f"{self.agent_memory_base_dir}/experience")
        AIStorage.get_instance().ensure_directory_exists(f"{self.agent_memory_base_dir}/contacts")
        AIStorage.get_instance().ensure_directory_exists(f"{self.agent_memory_base_dir}/relations")
        AIStorage.get_instance().ensure_directory_exists(f"{self.agent_memory_base_dir}/summary")

        self.memory_db:str = f"{self.agent_memory_base_dir}/memory.db"
        self.model_name:str = "gp4-1106-preview"
        self.threshold_hours = 72
        self.last_think_time : float = 0.0

        self.load_memory_meta()


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
    
    # return last record time
    async def load_records(self,starttime,tokenlimit=8000)->float:
        # 专用思路：做聊天记录/工作经验的整理
        # 通用思路：没有具体的目的，让Agent根据提示词自己工作（可能效果很差也可能很好）
        # 先实现通用思路
        msg_records = AIChatSession.load_message_records_by_agentid(self.agent_id,starttime,32,self.memory_db)
        work_records = self.load_worklogs(self.agent_id,token_limit=tokenlimit)
        pass

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
        #conn.close()

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
        #conn.close()

    def memory_meta_to_dict(self) -> Dict:
        return {
            "last_think_time" : self.last_think_time
        }
    
    def load_meta(self,Dict):
        self.last_think_time = Dict.get("last_think_time",0.0)
    
    def load_memory_meta(self):
        meta_file_path = f"{self.agent_memory_base_dir}/meta.json"
        try:
            with open(meta_file_path, mode='r') as file:
                meta = json.load(file)
                self.load_meta(meta)

        except Exception as e:
            logger.error(f"load memory meta failed: {e}")
            self.last_think_time = 0.0

    def save_memory_meta(self):
        meta_file_path = f"{self.agent_memory_base_dir}/meta.json"
        try:
            with open(meta_file_path, mode='w') as file:
                meta = self.memory_meta_to_dict()
                json.dump(meta,file)
        except Exception as e:
            logger.error(f"save memory meta failed: {e}")

    async def get_last_think_time(self)->float:
        return self.last_think_time

    async def set_last_think_time(self,last_time:float):
        self.last_think_time = last_time    
        self.save_memory_meta()

    async def get_contact_summary(self,contact_id:str) -> str:
        if contact_id is None:
            return "Contact id is None"
        
        result = {}
        contact_info:Contact = ContactManager.get_instance().find_contact_by_name(contact_id)
        if contact_info:
            result["name"] = contact_info.name
            result["relation"] = contact_info.relationship
            result["notes"]  = contact_info.notes

        summary_path = f"{self.agent_memory_base_dir}/contacts/{contact_id}.summary"
        try:
            async with aiofiles.open(summary_path, mode='r') as file:
                result["summary"] =  await file.read()
                
        except Exception as e:
            logger.error(f"read contact summary failed: {e}")
            
        return json.dumps(result,ensure_ascii=False)
    
    async def update_contact_summary(self,contact_id:str,summary:str):
        summary_path = f"{self.agent_memory_base_dir}/contacts/{contact_id}.summary"
        try:
            async with aiofiles.open(summary_path, mode='w') as file:
                await file.write(summary)
                return "OK"
        except Exception as e:
            logger.error(f"write contact summary failed: {e}")
            return "write contact summary failed: {e}"
    
    async def get_summary(self,object_name:str) -> str:
        summary_path = f"{self.agent_memory_base_dir}/{object_name}.summary"
        try:
            async with aiofiles.open(summary_path, mode='r') as file:
                return await file.read()
        except Exception as e:
            logger.error(f"read summary failed: {e}")
            return f"read summary failed: {e}"
        
    async def update_summary(self,object_name:str,summary:str) -> str:
        summary_path = f"{self.agent_memory_base_dir}/{object_name}.summary"
        try:
            async with aiofiles.open(summary_path, mode='w') as file:
                await file.write(summary)
                return "OK"
        except Exception as e:
            logger.error(f"write summary failed: {e}")
            return f"write summary failed: {e}"
    
    async def list_summary_object_names(self) -> List[str]:
        # list dir
        try:
            contents = os.listdir(self.agent_memory_base_dir)
            return [x for x in contents if x.endswith(".summary")]
        except Exception as e:
            logger.error(f"list summary object names failed: {e}")
            return []
        
    # means object1 feel object2 is ... 
    async def get_relation_summary(self,object_name1:str,object_name2:str) -> str:
        summary_path = f"{self.agent_memory_base_dir}/relations/{object_name1}.relation.{object_name2}.summary"
        try:
            async with aiofiles.open(summary_path, mode='r') as file:
                await file.read()
        except FileNotFoundError:
            return "no summary"
        except Exception as e:
            logger.error(f"read relation summary failed: {e}")
            return f"read relation summary failed: {e}"
        
    
    async def update_relation_summary(self,object_name1:str,object_name2:str,summary:Dict):
        summary_path = f"{self.agent_memory_base_dir}/relations/{object_name1}.relation.{object_name2}.summary"
        try:
            async with aiofiles.open(summary_path, mode='w') as file:
                await file.write(json.dumps(summary))
                return "OK"
        except Exception as e:
            logger.error(f"write relation summary failed: {e}")
            return "write relation summary failed: {e}"
    
    async def get_experience(self,topic_name:str) -> str:
        experience_path = f"{self.agent_memory_base_dir}/experience/{topic_name}.experience"
        try:
            async with aiofiles.open(experience_path, mode='r') as file:
                await file.read()
        except FileNotFoundError:
            return "no experience"
        except Exception as e:
            logger.error(f"read experience failed: {e}")
            return f"read experience failed: {e}"

    
    async def set_experience(self,topic_name:str,summary:str) -> str:
        experience_path = f"{self.agent_memory_base_dir}/experience/{topic_name}.experience"
        try:
            async with aiofiles.open(experience_path, mode='w') as file:
                await file.write(summary)
                return "OK"
        except Exception as e:
            logger.error(f"write experience failed: {e}")
            return "write experience failed: {e}"
    
    async def list_experience(self) -> List[str]:
        dir_path = f"{self.agent_memory_base_dir}/experience"
        try:
            contents = os.listdir(dir_path)
            return [x for x in contents if x.endswith(".experience")]
        except Exception as e:
            logger.error(f"list experience failed: {e}")
            return []

    @staticmethod
    def register_ai_functions():
        async def get_contact_summary(parameters):
            agent_memory:AgentMemory = parameters.get("_agent_memory")
            contact_name = parameters.get("contact_name")
            return await agent_memory.get_contact_summary(contact_name)
        parameters = ParameterDefine.create_parameters({
            "contact_name": {"type": "string", "description": "contact name"}
        })
        get_contact_summary_func = SimpleAIFunction("agent.memory.get_contact_summary",
                                                    "get contact summary",
                                                    get_contact_summary,
                                                    parameters)
        GlobaToolsLibrary.register_tool_function(get_contact_summary_func)

        async def update_contact_summary(parameters):
            agent_memory:AgentMemory = parameters.get("_agent_memory")
            contact_name = parameters.get("contact_name")
            summary = parameters.get("summary")
            return await agent_memory.update_contact_summary(contact_name,summary)
        parameters = ParameterDefine.create_parameters({
            "contact_name": {"type": "string", "description": "contact name"},
            "summary": {"type": "string", "description": "new summary"}
        })
        update_contact_summary_func = SimpleAIFunction("agent.memory.update_contact_summary",
                                                    "update contact summary",
                                                    update_contact_summary,
                                                    parameters)
        GlobaToolsLibrary.register_tool_function(update_contact_summary_func)

        async def get_summary(parameters):
            agent_memory:AgentMemory = parameters.get("_agent_memory")
            object_name = parameters.get("object_name")
            return await agent_memory.get_summary(object_name)
        parameters = ParameterDefine.create_parameters({
            "object_name": {"type": "string", "description": "object name"}
        })
        get_summary_func = SimpleAIFunction("agent.memory.get_summary",
                                                    "get summary of sth",
                                                    get_summary,
                                                    parameters)
        GlobaToolsLibrary.register_tool_function(get_summary_func)

        async def update_summary(parameters):
            agent_memory:AgentMemory = parameters.get("_agent_memory")
            object_name = parameters.get("object_name")
            summary = parameters.get("summary")
            return await agent_memory.update_summary(object_name,summary)
        parameters = ParameterDefine.create_parameters({
            "object_name": {"type": "string", "description": "object name"},
            "summary": {"type": "string", "description": "new summary"}
        })
        update_summary_func = SimpleAIFunction("agent.memory.update_summary",
                                                    "update summary of sth",
                                                    update_summary,
                                                    parameters)
        GlobaToolsLibrary.register_tool_function(update_summary_func)

        async def list_summary_object_names(parameters):
            agent_memory:AgentMemory = parameters.get("_agent_memory")
            return await agent_memory.list_summary_object_names()
        parameters = ParameterDefine.create_parameters({})
        list_summary_object_names_func = SimpleAIFunction("agent.memory.list_summary",
                                                    "list summary object names",
                                                    list_summary_object_names,
                                                    parameters)
        GlobaToolsLibrary.register_tool_function(list_summary_object_names_func)

        async def get_relation_summary(parameters):
            agent_memory:AgentMemory = parameters.get("_agent_memory")
            object_name1 = parameters.get("object1_name")
            object_name2 = parameters.get("object2_name")
            return await agent_memory.get_relation_summary(object_name1,object_name2)
        parameters = ParameterDefine.create_parameters({
            "object1_name": {"type": "string", "description": "object name1"},
            "object2_name": {"type": "string", "description": "object name2"}
        })
        get_relation_summary_func = SimpleAIFunction("agent.memory.get_relation_summary",
                                                    "object1 feel object2 is ...",
                                                    get_relation_summary,
                                                    parameters)
        GlobaToolsLibrary.register_tool_function(get_relation_summary_func)

        async def update_relation_summary(parameters):
            agent_memory:AgentMemory = parameters.get("_agent_memory")
            object_name1 = parameters.get("object1_name")
            object_name2 = parameters.get("object2_name")
            summary = parameters.get("summary")
            return await agent_memory.update_relation_summary(object_name1,object_name2,summary)
        parameters = ParameterDefine.create_parameters({
            "object1_name": {"type": "string", "description": "object name1"},
            "object2_name": {"type": "string", "description": "object name2"},
            "summary": {"type": "string", "description": "new summary"}
        })
        update_relation_summary_func = SimpleAIFunction("agent.memory.update_relation_summary",
                                                    "object1 feel object2 is ...",
                                                    update_relation_summary,
                                                    parameters)
        GlobaToolsLibrary.register_tool_function(update_relation_summary_func)

        async def get_experience(parameters):
            agent_memory:AgentMemory = parameters.get("_agent_memory")
            topic_name = parameters.get("topic_name")
            return await agent_memory.get_experience(topic_name)
        parameters = ParameterDefine.create_parameters({
            "topic_name": {"type": "string", "description": "topic name"}
        })
        get_experience_func = SimpleAIFunction("agent.memory.get_experience",
                                                    "get experience",
                                                    get_experience,
                                                    parameters)
        GlobaToolsLibrary.register_tool_function(get_experience_func)

        async def set_experience(parameters):
            agent_memory:AgentMemory = parameters.get("_agent_memory")
            topic_name = parameters.get("topic_name")
            summary = parameters.get("summary")
            return await agent_memory.set_experience(topic_name,summary)
        parameters = ParameterDefine.create_parameters({
            "topic_name": {"type": "string", "description": "topic name"},
            "summary": {"type": "string", "description": "new summary"}
        })
        set_experience_func = SimpleAIFunction("agent.memory.set_experience",
                                                    "set experience",
                                                    set_experience,
                                                    parameters)
        GlobaToolsLibrary.register_tool_function(set_experience_func)

        async def list_experience(parameters):
            agent_memory:AgentMemory = parameters.get("_agent_memory")
            return await agent_memory.list_experience()
        parameters = ParameterDefine.create_parameters({})
        list_experience_func = SimpleAIFunction("agent.memory.list_experience",
                                                    "list exist experience topics",
                                                    list_experience,
                                                    parameters)
        GlobaToolsLibrary.register_tool_function(list_experience_func)

        

    
    
    

    
    
