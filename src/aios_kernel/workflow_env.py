
from datetime import datetime
import asyncio
import sqlite3 # Because sqlite3 IO operation is small, so we can use sqlite3 directly.(so we don't need to use async sqlite3 now)
from sqlite3 import Error
import threading
import logging
from typing import Optional
from .environment import Environment,EnvironmentEvent
from .ai_function import SimpleAIFunction

logger = logging.getLogger(__name__)


class CalenderEvent(EnvironmentEvent):
    def __init__(self,data) -> None:
        super().__init__()
        self.event_name = "timer"
        self.data = data

    def display(self) -> str:
        return f"#event timer:{self.data}"    
    
# AI Calender GOAL: Let user use "create notify after 2 days" to create a timer event
class CalenderEnvironment(Environment):
    def __init__(self, env_id: str) -> None:
        super().__init__(env_id)
        self.is_run = False

        self.add_ai_function(SimpleAIFunction("get_time",
                                        "get current time",
                                        self._get_now))

    def _do_get_value(self,key:str) -> Optional[str]:
        return None

    def start(self) -> None:
        if self.is_run:
            return 
        self.is_run = True

        self.register_get_handler("now",self.get_now)
        async def timer_loop():
            while True:
                if self.is_run == False:
                    break
                
                await asyncio.sleep(1.0)
                now = datetime.now()
                formatted_time = now.strftime('%Y-%m-%d %H:%M:%S')
                env_event:CalenderEvent = CalenderEvent(formatted_time)
                await self.fire_event("timer",env_event)

            return

        asyncio.create_task(timer_loop())

    def stop(self):
        self.is_run = False

    def get_now(self)->str:
        now = datetime.now()
        formatted_time = now.strftime('%Y-%m-%d %H:%M:%S')
        return formatted_time     

    async def _get_now(self) -> str:
        now = datetime.now()
        formatted_time = now.strftime('%Y-%m-%d %H:%M:%S')
        return formatted_time
    
# Default Workflow Environment(Context)
class WorkflowEnvironment(Environment):
    def __init__(self, env_id: str,db_file:str) -> None:
        super().__init__(env_id)
        self.db_file = db_file
        self.local = threading.local()
        self.table_name = "WorkflowEnv_" + env_id


    def _get_conn(self):
        """ get db connection """
        if not hasattr(self.local, 'conn'):
            self.local.conn = self._create_connection()
        return self.local.conn
    
    def _create_connection(self):
        """ create a database connection to a SQLite database """
        conn = None
        try:
            conn = sqlite3.connect(self.db_file)
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
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS """ + self.table_name + """ (
                    EnvKey TEXT PRIMARY KEY,
                    EnvValue TEXT,
                    UpdateTime TEXT
                );
            """)
            conn.commit()
        except Error as e:
            logging.error("Error occurred while creating tables: %s", e)
    
    def _do_get_value(self, key: str) -> str | None:
        try:
            conn = self._get_conn()
            c = conn.cursor()
            c.execute("SELECT EnvValue FROM " + self.table_name +" WHERE EnvKey = ?", (key,))
            value = c.fetchone()
            if value is None:
                return None
            return value[0]
        except Error as e:
            logging.error(f"Error occurred while _do_get_value{key}: {e}")
            return None

    def set_value(self, key: str, str_value: str, is_storage:bool=True):
        super().set_value(key,str_value)
        if is_storage is False:
            return
        
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT OR REPLACE INTO """ + self.table_name+ """ (EnvKey, EnvValue, UpdateTime)
                VALUES (?, ?, ?) 
            """, (key, str_value, datetime.now()))
            conn.commit()
            return 0  # return 0 if successful
        except Error as e:
            logging.error(f"Error occurred while update env{self.env_id}.{key} ,error:{e}")

    def get_functions(self):
        pass

