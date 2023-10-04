
import sqlite3 # Because sqlite3 IO operation is small, so we can use sqlite3 directly.(so we don't need to use async sqlite3 now)
from sqlite3 import Error
import logging
import threading
import datetime
import uuid
import json

from .agent_message import AgentMsgType, AgentMsg, AgentMsgStatus

class ChatSessionDB:
    def __init__(self, db_file):
        """ initialize db connection """
        self.local = threading.local()
        self.db_file = db_file
        self._get_conn()

    def _get_conn(self):
        """ get db connection """
        if not hasattr(self.local, 'conn'):
            self.local.conn = self._create_connection(self.db_file)
        return self.local.conn

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

    def close(self):
        if not hasattr(self.local, 'conn'):
            return
        self.local.conn.close()

    def _create_table(self, conn):
        """ create table """
        try:
            # create sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ChatSessions (
                    SessionID TEXT PRIMARY KEY,
                    SessionOwner TEXT,
                    SessionTopic TEXT,
                    StartTime TEXT,
                    SummarizePos INTEGER,
                    Summary TEXT
                );
            """)

            # create messages table
            # reciver_id could be None

            conn.execute("""
                CREATE TABLE IF NOT EXISTS Messages (
                    MessageID TEXT PRIMARY KEY,
                    SessionID TEXT,
                    MsgType INTEGER,
                    PrevMsgID TEXT,
                    QuoteMsgID TEXT,
                    RelyMsgID TEXT,
                    
                    SenderID TEXT, 
                    ReceiverID TEXT,
                    Timestamp TEXT,
                    
                    Topic TEXT,
                    Mentions TEXT,
                    ContentMIME TEXT,
                    Content TEXT,
                    
                    ActionName TEXT,
                    ActionParams TEXT,
                    ActionResult TEXT,
                    DoneTime TEXT,     
                         
                    Status INTEGER
                );
            """)
            conn.commit()
        except Error as e:
            logging.error("Error occurred while creating tables: %s", e)

    def insert_chatsession(self, session_id, session_owner,session_topic, start_time):
        """ insert a new session into the ChatSessions table """
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT INTO ChatSessions (SessionID, SessionOwner,SessionTopic, StartTime,SummarizePos,Summary)
                VALUES (?,?, ?, ?,0,"")
            """, (session_id, session_owner,session_topic, start_time))
            conn.commit()
            return 0  # return 0 if successful
        except Error as e:
            logging.error("Error occurred while inserting session: %s", e)
            return -1  # return -1 if an error occurs

    def insert_message(self, msg:AgentMsg):
        """ insert a new message into the Messages table """
        try:
            action_name = None
            action_params = None
            action_result = None
            mentions = None
            if msg.mentions:
                mentions = json.dumps(msg.mentions)

            match msg.msg_type:
                case AgentMsgType.TYPE_MSG:
                    pass
                case AgentMsgType.TYPE_ACTION:
                    action_name = msg.func_name
                    action_params = json.dumps(msg.args)
                    action_result = msg.result_str
                case AgentMsgType.TYPE_INTERNAL_CALL:
                    action_name = msg.func_name
                    action_params = json.dumps(msg.args)
                    action_result = msg.result_str
                case AgentMsgType.TYPE_EVENT:
                    action_name = msg.event_name
                    action_params = json.dumps(msg.event_args)


            conn = self._get_conn()
            conn.execute("""
                INSERT INTO Messages (MessageID, SessionID, MsgType, PrevMsgID, SenderID, ReceiverID, Timestamp, Topic,Mentions,ContentMIME,Content,ActionName,ActionParams,ActionResult,DoneTime,Status)
                VALUES (?, ?, ?, ?, ?, ?, ?,?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (msg.msg_id, msg.session_id, msg.msg_type.value, msg.prev_msg_id, msg.sender, msg.target, msg.create_time, msg.topic,mentions,msg.body_mime,msg.body,action_name,action_params,action_result,msg.done_time,msg.status.value))
            conn.commit()

            if msg.inner_call_chain:
                for inner_call in msg.inner_call_chain:
                    self.insert_message(inner_call)

            return 0  # return 0 if successful
        except Error as e:
            logging.error("Error occurred while inserting message: %s", e)
            return -1  # return -1 if an error occurs

    def get_chatsession_by_id(self, session_id):
        """Get a message by its ID"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM ChatSessions WHERE SessionID = ?", (session_id,))
        chatsession = c.fetchone()
        return chatsession

    def get_chatsession_by_owner_topic(self, owner_id, topic):
        """Get a chatsession by its owner and topic"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM ChatSessions WHERE SessionOwner = ? AND SessionTopic = ?", (owner_id,topic))
        chatsession = c.fetchone()
        return chatsession

    def list_chatsessions(self, owner_id, limit, offset):
        """ retrieve sessions with pagination """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SessionID FROM ChatSessions
                WHERE SessionOwner = ?           
                ORDER BY StartTime DESC
                LIMIT ? OFFSET ? 
            """, (owner_id,limit, offset))
            results = cursor.fetchall()
            #self.close()
            return results  # return 0 and the result if successful
        except Error as e:
            logging.error("Error occurred while getting sessions: %s", e)
            return -1, None  # return -1 and None if an error occurs

    def get_message_by_id(self, message_id):
        """Get a message by its ID"""
        conn =self._get_conn()
        c = conn.cursor()
        c.execute("SELECT MessageID, SessionID, MsgType, PrevMsgID, SenderID, ReceiverID, Timestamp, Topic,Mentions,ContentMIME,Content,ActionName,ActionParams,ActionResult,DoneTime,Status FROM Messages WHERE MessageID = ?", (message_id,))
        message = c.fetchone()
        return message

    # read message from begin->now
    def read_message(self,session_id,limit,offset):
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MessageID, SessionID, MsgType, PrevMsgID, SenderID, ReceiverID, Timestamp, Topic,Mentions,ContentMIME,Content,ActionName,ActionParams,ActionResult,DoneTime,Status FROM Messages
                WHERE SessionID = ?
                ORDER BY Timestamp 
                LIMIT ? OFFSET ?
            """, (session_id, limit, offset))
            results = cursor.fetchall()
            #self.close()
            return results  # return 0 and the result if successful
        except Error as e:
            logging.error("Error occurred while getting messages: %s", e)
            return -1, None  # return -1 and None if an error occurs
        
    # read message from  now->beign    
    def get_messages(self, session_id, limit, offset):
        """ retrieve messages of a session with pagination """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MessageID, SessionID, MsgType, PrevMsgID, SenderID, ReceiverID, Timestamp, Topic,Mentions,ContentMIME,Content,ActionName,ActionParams,ActionResult,DoneTime,Status FROM Messages
                WHERE SessionID = ?
                ORDER BY Timestamp DESC
                LIMIT ? OFFSET ?
            """, (session_id, limit, offset))
            results = cursor.fetchall()
            #self.close()
            return results  # return 0 and the result if successful
        except Error as e:
            logging.error("Error occurred while getting messages: %s", e)
            return -1, None  # return -1 and None if an error occurs

    def update_message_status(self, message_id, status):
        """ update the status of a message """
        try:
            conn = self._get_conn()
            conn.execute("""
                UPDATE Messages
                SET Status = ?
                WHERE MessageID = ?
            """, (status, message_id))
            conn.commit()
            return 0  # return 0 if successful
        except Error as e:
            logging.error("Error occurred while updating message status: %s", e)
            return -1  # return -1 if an error occurs

    def update_session_summary(self, session_id, summarize_pos, summary):
        """ update the summary of a session """
        try:
            conn = self._get_conn()
            conn.execute("""
                UPDATE ChatSessions
                SET SummarizePos = ?, Summary = ?
                WHERE SessionID = ?
            """, (summarize_pos, summary, session_id))
            conn.commit()
            return 0  # return 0 if successful
        except Error as e:
            logging.error("Error occurred while updating session summary: %s", e)
            return -1

# chat session store the chat history between owner and agent
# chat session might be large, so can read / write at stream mode.
class AIChatSession:
    _dbs = {}
    #@classmethod
    #async def get_session_by_id(cls,session_id:str,db_path:str):
    #    db = cls._dbs.get(db_path)
    #    if db is None:
    #        db = ChatSessionDB(db_path)
    #        cls._dbs[db_path] = db
    #    db.get_chatsession_by_id(session_id)
    #    #result = AIChatSession()

    @classmethod
    def get_session(cls,owner_id:str,session_topic:str,db_path:str,auto_create = True) -> 'AIChatSession':
        db = cls._dbs.get(db_path)
        if db is None:
            db = ChatSessionDB(db_path)
            cls._dbs[db_path] = db

        result = None
        session = db.get_chatsession_by_owner_topic(owner_id,session_topic)
        if session is None:
            if auto_create:
                session_id = "CS#" + uuid.uuid4().hex
                db.insert_chatsession(session_id,owner_id,session_topic,datetime.datetime.now())
                result = AIChatSession(owner_id,session_id,db)
        else:
            result = AIChatSession(owner_id,session[0],db)
            result.topic = session_topic
            result.summarize_pos = session[4]
            result.summary = session[5]

        return result
    
    @classmethod
    def get_session_by_id(cls,session_id:str,db_path:str)->'AIChatSession':
        db = cls._dbs.get(db_path)
        if db is None:
            db = ChatSessionDB(db_path)
            cls._dbs[db_path] = db

        result = None
        session = db.get_chatsession_by_id(session_id)
        if session is None:
            return None
        else:
            result = AIChatSession(session[1],session[0],db)
            result.topic = session[2]
            result.summarize_pos = session[4]
            result.summary = session[5]

        return result        

    @classmethod
    def list_session(cls,owner_id:str,db_path:str) -> list[str]:
        db = cls._dbs.get(db_path)
        if db is None:
            db = ChatSessionDB(db_path)
            cls._dbs[db_path] = db

        result = db.list_chatsessions(owner_id,16,0)
        result_ids = []
        for r in result:
            result_ids.append(r[0])
        return result_ids    


    def __init__(self,owner_id:str, session_id:str, db:ChatSessionDB) -> None:
        self.owner_id :str = owner_id
        self.session_id : str = session_id
        self.db : ChatSessionDB = db

        self.topic : str = None
        self.start_time : str = None
        self.summarize_pos : int = 0
        self.summary = None

    def get_owner_id(self) -> str:
        return self.owner_id

    def read_history(self, number:int=10,offset=0,order="revers") -> [AgentMsg]:
        if order == "revers":
            msgs = self.db.get_messages(self.session_id, number, offset)
        else:
            msgs = self.db.read_message(self.session_id, number, offset)
            
        result = []
        for msg in msgs:
            agent_msg = AgentMsg()
            agent_msg.msg_id = msg[0]
            agent_msg.session_id = msg[1]
            agent_msg.msg_type = AgentMsgType(msg[2])
            agent_msg.prev_msg_id = msg[3]
            agent_msg.sender = msg[4]
            agent_msg.target = msg[5]
            agent_msg.create_time = msg[6]
            agent_msg.topic = msg[7]
            if msg[8] is not None:
                agent_msg.mentions = json.loads(msg[8])
            agent_msg.body_mime = msg[9]
            agent_msg.body = msg[10]
            agent_msg.func_name = msg[11]
            if msg[12] is not None:
                agent_msg.args = json.loads(msg[12])
            agent_msg.result_str = msg[13]
            agent_msg.done_time = msg[14]
            agent_msg.status = AgentMsgStatus(msg[15])

            result.append(agent_msg)
        return result

    def append(self,msg:AgentMsg) -> None:
        msg.session_id = self.session_id
        self.db.insert_message(msg)


    def update_think_progress(self,progress:int,new_summary:str) -> None:
        self.db.update_session_summary(self.session_id,progress,new_summary)
        self.summarize_pos = progress
        self.summary = new_summary

    #def attach_event_handler(self,handler) -> None:
    #    """chat session changed event handler"""
    #    pass

    #TODO : add iterator interface for read chat history
