# pylint:disable=E0402
from datetime import datetime
import asyncio
import json
import sqlite3 # Because sqlite3 IO operation is small, so we can use sqlite3 directly.(so we don't need to use async sqlite3 now)
from sqlite3 import Error
import threading
import logging
from typing import Optional
import aiosqlite

from ..agent.llm_context import GlobaToolsLibrary
from ..proto.compute_task import *
from ..proto.ai_function import *
from ..frame.compute_kernel import ComputeKernel
from ..frame.contact_manager import ContactManager,Contact
from ..storage.storage import AIStorage

from .environment import SimpleEnvironment, CompositeEnvironment
from ..ai_functions.script_to_speech_function import ScriptToSpeechFunction
from ..ai_functions.image_2_text_function import Image2TextFunction

logger = logging.getLogger(__name__)

class CalenderEvent(SimpleEnvironment):
    def __init__(self,data) -> None:
        super().__init__()
        self.event_name = "timer"
        self.data = data

    def display(self) -> str:
        return f"#event timer:{self.data}"

# AI Calender GOAL: Let user use "create notify after 2 days" to create a timer event
class CalenderEnvironment(SimpleEnvironment):
    def __init__(self, env_id: str) -> None:
        super().__init__(env_id)
        self.db_file = AIStorage.get_instance().get_myai_dir() / "calender.db"
        self.is_run = False
        gl = GlobaToolsLibrary.get_instance()

        gl.register_tool_function(SimpleAIFunction("system.now",
                                        "get current time",
                                        self._get_now))
        
        get_param = ParameterDefine.create_parameters({
            "start_time": "start time (UTC) of event",
            "end_time": "end time (UTC) of event"
        })
        gl.register_tool_function(SimpleAIFunction("system.calender.get_events",
                                              "get events in calender by time range",
                                              self._get_events_by_time_range,get_param))

        add_param = ParameterDefine.create_parameters({
            "title": "title of event",
            "start_time": "start time (UTC) of event",
            "end_time": "end time (UTC) of event",
            "participants": "participants of event",
            "location": "location of event",
            "details": "details of event"
        })
        gl.register_tool_function(SimpleAIFunction("system.calender.add_event",
                                        "add event to calender",
                                        self._add_event,add_param))

        delete_param = ParameterDefine.create_parameters({
            "event_id": "id of event"
        })
        gl.register_tool_function(SimpleAIFunction("system.calender.delete_event",
                                        "delete event from calender",
                                        self._delete_event,delete_param))

        update_param = ParameterDefine.create_parameters({
            "event_id": "id of event",
            "new_title": "new title of event",
            "new_participants": "new participants of event",
            "new_location": "new location of event",
            "new_details": "new details of event",
            "start_time": "new start time (UTC) of event",
            "end_time": "new end time (UTC) of event"
        })
        gl.register_tool_function(SimpleAIFunction("system.calender.update_event",
                                        "update event in calender",
                                        self._update_event,update_param))


    async def init_db(self):
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    start_time DATETIME,
                    end_time DATETIME,
                    participants TEXT,
                    location TEXT,
                    details TEXT
                );
            """)
            await db.commit()

    async def _add_event(self,title, start_time, end_time, participants=None, location=None, details=None):
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute("""
                INSERT INTO events (title, start_time, end_time, participants, location, details)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (title, start_time, end_time, participants, location, details))
            await db.commit()
            return f"execute add_event OK,event '{title}' already add to calender!"

    async def _search_events(self,query):
        async with aiosqlite.connect(self.db_file) as db:
            cursor = await db.execute("""
                SELECT id,title, start_time, end_time, participants, location, details FROM events
                WHERE title LIKE ? OR participants LIKE ? OR location LIKE ? OR details LIKE ?;
            """, (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"))
            rows = await cursor.fetchall()

            result = {}
            for row in rows:
                _event = {}
                _event["title"] = row[1]
                _event["start_time"] = row[2]
                _event["end_time"] = row[3]
                _event["participants"] = row[4]
                _event["location"] = row[5]
                _event["details"] = row[6]
                result[row[0]] = _event
            return json.dumps(result, indent=4, sort_keys=True,ensure_ascii=False)

    async def _get_events_by_time_range(self,start_time, end_time):
        async with aiosqlite.connect(self.db_file) as db:
            cursor = await db.execute("""
                SELECT id,title, start_time, end_time, participants, location, details FROM events
                WHERE start_time >= ? AND end_time <= ?;
            """, (start_time, end_time))
            rows = await cursor.fetchall()

            result = {}
            have_result = False
            for row in rows:
                have_result = True
                _event = {}
                _event["title"] = row[1]
                _event["start_time"] = row[2]
                _event["end_time"] = row[3]
                _event["participants"] = row[4]
                _event["location"] = row[5]
                _event["details"] = row[6]
                result[row[0]] = _event

            if not have_result:
                return "No event."

            return json.dumps(result, indent=4, sort_keys=True,ensure_ascii=False)

    async def _update_event(self,event_id, new_title=None, new_participants=None, new_location=None, new_details=None ,start_time=None, end_time=None):
        fields_to_update = []
        values = []

        if new_title is not None:
            fields_to_update.append("title = ?")
            values.append(new_title)

        if new_participants is not None:
            fields_to_update.append("participants = ?")
            values.append(new_participants)

        if new_location is not None:
            fields_to_update.append("location = ?")
            values.append(new_location)

        if new_details is not None:
            fields_to_update.append("details = ?")
            values.append(new_details)

        if start_time is not None:
            fields_to_update.append("start_time = ?")
            values.append(start_time)

        if end_time is not None:
            fields_to_update.append("end_time = ?")
            values.append(end_time)

        if not fields_to_update:
            return "No fields to update."

        sql_update_query = f"""
            UPDATE events
            SET {', '.join(fields_to_update)}
            WHERE id = ?;
        """

        values.append(event_id)

        async with aiosqlite.connect(self.db_file) as db:
            await db.execute(sql_update_query, values)
            await db.commit()
            return "update ok"

    async def _delete_event(self,event_id):
        async with aiosqlite.connect(self.db_file) as db:
            await db.execute("""
                DELETE FROM events
                WHERE id = ?;
            """, (event_id,))
            await db.commit()
            return "Delete event ok"

    def _do_get_value(self,key:str) -> Optional[str]:
        return None

    async def _get_contact(self,name:str) -> str:
        cm = ContactManager.get_instance()
        contact : Contact = cm.find_contact_by_name(name)
        if contact:
            s = json.dumps(contact.to_dict(),ensure_ascii=False)
            return f"Execute get_contact OK , contact {name} is {s}"
        else:
            return f"Execute get_contact OK , contact {name} not found!"

    async def _set_contact(self,name:str,contact_info:str) -> str:
        cm = ContactManager.get_instance()
        contact = cm.find_contact_by_name(name)
        contact_info = json.loads(contact_info)
        if contact is None:
            contact = Contact(name)
            contact.email = contact_info.get("email")
            contact.telegram = contact_info.get("telegram")
            contact.notes = contact_info.get("notes")
            contact.added_by = self.env_id

            cm.add_contact(name,contact)

            return f"Execute set_contact OK , new contact {name} added!"
        else:
            if contact_info.get("email") is not None:
                contact.email = contact_info.get("email")
            if contact_info.get("telegram") is not None:
                contact.telegram = contact_info.get("telegram")
            if contact_info.get("notes") is not None:
                contact.notes = contact_info.get("notes")

            contact.added_by = self.env_id
            cm.set_contact(name,contact)

            return f"Execute set_contact OK , contact {name} updated!"

    async def start(self) -> None:
        if self.is_run:
            return
        self.is_run = True
        await self.init_db()

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


    async def _paint(self, prompt, model_name = None) -> str:
        result = await ComputeKernel.get_instance().do_text_2_image(prompt, model_name)
        if result.result_code == ComputeTaskResultCode.ERROR:
            return f"exec paint failed. err:{result.error_str}"
        else:
            return f'exec paint OK, saved as a local file, path is: {result.result["file"]}'


class PaintEnvironment(SimpleEnvironment):
    def __init__(self, env_id: str) -> None:
        super().__init__(env_id)

    

    
    def register_functions(self):
        paint_param = ParameterDefine.create_parameters({
            "prompt": "Description of the content of the painting",
        })
        GlobaToolsLibrary.get_instance().register_tool_function(SimpleAIFunction("aigc.text_2_image",
                                        "Draw a picture according to the description",
                                        self._paint,paint_param))

    def _do_get_value(self,key:str) -> Optional[str]:
        return None


    async def _paint(self, prompt, model_name = None, negative_prompt = None) -> str:
        result = await ComputeKernel.get_instance().do_text_2_image(prompt, model_name, negative_prompt)
        if result.result_code == ComputeTaskResultCode.ERROR:
            return f"exec paint failed. err:{result.error_str}"
        else:
            return f'exec paint OK, saved as a local file, path is: {result.result["file"]}'


# Default Workflow Environment(Context)
class WorkflowEnvironment(CompositeEnvironment):
    def __init__(self, env_id: str,db_file:str) -> None:
        super().__init__(env_id)
        self.db_file = db_file
        self.local = threading.local()
        self.table_name = "WorkflowEnv_" + env_id
        # self.add_ai_function(ScriptToSpeechFunction())
        # self.add_ai_function(Image2TextFunction())


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
