import datetime
import sqlite3
import os
from . import ObjectID, KnowledgeStore
from enum import Enum

class KnowledgePipelineJournal:
    def __init__(self, time: datetime.datetime, object_id: str, input: str, parser: str):
        self.time = time
        self.object_id = None if object_id is None else ObjectID.from_base58(object_id)
        self.input = input
        self.parser = parser
    
    def is_finish(self) -> bool:
        return self.object_id is None

    def get_input(self) -> str:
        return self.input
    
    def get_parser(self) -> str:
        return self.parser
    
    def __str__(self) -> str:
        if self.is_finish():
            return f"{self.time}: finished)"
        else:
            return f"{self.time}: object:{self.object_id} input:{self.input}, parser:{self.parser})"

# init sqlite3 client
class KnowledgePipelineJournalClient:
    def __init__(self, pipeline_path: str = None):
        if not os.path.exists(pipeline_path):
            os.makedirs(pipeline_path)
        self.journal_path = os.path.join(pipeline_path, "journal.db")
    
        conn = sqlite3.connect(self.journal_path)
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                time DATETIME DEFAULT CURRENT_TIMESTAMP,  
                object_id TEXT, 
                input TEXT, 
                parser TEXT)'''
        )
        conn.commit()

    def insert(self, object_id: ObjectID, input: str, parser: str, timestamp: datetime.datetime = None):
        timestamp = datetime.datetime.now() if timestamp is None else timestamp
        conn = sqlite3.connect(self.journal_path)
        conn.execute(
            "INSERT INTO journal (time, object_id, input, parser) VALUES (?, ?, ?, ?)",
            (timestamp, str(object_id), input, parser),
        )
        conn.commit()
          
    def latest_journals(self, topn) -> [KnowledgePipelineJournal]:
        conn = sqlite3.connect(self.journal_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM journal ORDER BY id DESC LIMIT ?", (topn,))
        return [KnowledgePipelineJournal(time, object_id, input, parser) for (_, time, object_id, input, parser) in cursor.fetchall()]

class KnowledgePipelineEnvironment:
    def __init__(self, pipeline_path: str):
        self.knowledge_store = KnowledgeStore()
        if not os.path.exists(pipeline_path):
            os.makedirs(pipeline_path)
        self.pipeline_path = pipeline_path
        self.journal = KnowledgePipelineJournalClient(pipeline_path)

    def get_journal(self) -> KnowledgePipelineJournalClient:
        return self.journal
    
    def get_knowledge_store(self) -> KnowledgeStore:
        return self.knowledge_store

class KnowledgePipelineState(Enum):
    INIT = 0
    RUNNING = 1
    STOPPED = 2
    FINISHED = 3

class KnowledgePipeline:
    def __init__(self, name: str, env: KnowledgePipelineEnvironment, input_init, input_params, parser_init, parser_params):
        self.name = name
        self.state = KnowledgePipelineState.INIT
        self.input_init = input_init
        self.input_params = input_params
        self.parser_init = parser_init
        self.parser_params = parser_params
        self.env = env
        self.input = None
        self.parser = None

    def get_name(self):
        return self.name

    def get_journal(self) -> KnowledgePipelineJournalClient:
        return self.env.journal
        
    async def run(self):
        if self.state == KnowledgePipelineState.INIT:
            self.input = self.input_init(self.env, self.input_params)
            self.parser = self.parser_init(self.env, self.parser_params)
            self.state = KnowledgePipelineState.RUNNING
        if self.state == KnowledgePipelineState.RUNNING:
            async for input in self.input.next():
                if input is None:
                    self.state = KnowledgePipelineState.FINISHED
                    self.env.journal.insert(None, "finished", "finished")
                    return 
                (object_id, input_journal) = input
                if object_id is not None:
                    parser_journal = await self.parser.parse(object_id)
                    self.env.journal.insert(object_id, input_journal, parser_journal)
                else:
                    return
        if self.state == KnowledgePipelineState.STOPPED:
            return 
        if self.state == KnowledgePipelineState.FINISHED:
            return 


    