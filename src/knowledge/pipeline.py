
# class KnowledgePipelineTemplate
import runpy
import toml
import datetime
import sqlite3
import os
from . import ObjectID, KnowledgeStore
import asyncio

class KnowledgePipelineJournal:
    def __init__(self, time: datetime.datetime, object_id: str, input: str, parser: str):
        self.time = time
        self.object_id = None if object_id is None else ObjectID.from_base58(object_id)
        self.input = input
        self.parser = parser
    
    def is_finish(self) -> bool:
        self.object_id is None

    

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
            "INSERT INTO journal (time, object_id, input, parser) VALUES (?, ?, ?)",
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
        self.knowledge_base = KnowledgeStore()
        self.pipeline_path = pipeline_path
        self.journal = KnowledgePipelineJournalClient(pipeline_path)

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
        
    async def run(self):
        if self.state == KnowledgePipelineState.INIT:
            self.input = self.input_init(self.env, self.input_params)
            self.parser = self.parser_init(self.env, self.parser_params)
            self.state = KnowledgePipelineState.RUNNING
        if self.state == KnowledgePipelineState.RUNNING:
            for input in await self.input.next():
                if input is None:
                    self.state = KnowledgePipelineState.FINISHED
                    self.env.journal.insert(None, "finished", "finished")
                    return 
                (object_id, input_journal) = input
                if object_id is None:
                    parser_journal = await self.parser.parse(object_id)
                    self.env.journal.insert(object_id, input_journal, parser_journal)
        if self.state == KnowledgePipelineState.STOPPED:
            return 
        if self.state == KnowledgePipelineState.FINISHED:
            return 

class KnowledgePipelineManager:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.input_modules = {}
        self.parser_modules = {}
        self.pipelines = {
            "names": {},
            "running": []
        }
        from .input import local_dir
        self.register_input("local_dir", local_dir.init)

    def register_input(self, name: str, init_method):
        self.input_modules[name] = init_method
        
    def register_parser(self, name: str, parser_method):
        self.parser_modules[name] = parser_method

    def add_pipeline(self, config: dict, path: str):
        name = config["name"]
        if name in self.pipelines["names"]:
            return
        
        input_module = self.input_modules[config["input"]["module"]]
        _, ext = os.path.splitext(input_module)
        if ext == ".py":
            input_module = os.path.abspath(path, input_module)
            input_init = runpy.run_path(input_module)["init"]
        else:
            input_init = self.input_modules.get(input_module)
        input_params = config["input"]["params"]

        parser_module = self.parser_modules[config["parser"]["module"]]
        _, ext = os.path.splitext(parser_module)
        if ext == ".py":
            parser_module = os.path.abspath(path, parser_module)
            parser_init = runpy.run_path(parser_module)["init"]
        else:
            parser_init = self.parser_modules.get(parser_module)
        parser_params = config["parser"]["params"]


        data_path = self.root_dir / name
        env = KnowledgePipelineEnvironment(data_path)
        pipeline = KnowledgePipeline(name, env, input_init, input_params, parser_init, parser_params)
        self.pipelines["names"][name] = pipeline
        self.pipelines["running"].append(pipeline)

    async def run(self):
        while True:
            for pipeline in self.pipelines["running"]:
                await pipeline.run()
            await asyncio.sleep(5)

    def load_dir(self, root: str):
        config_path = os.path.join(root, "pipelines.toml")
        with open(config_path, "r") as f:
            config = toml.load(f)
        for path in config["pipelines"]:
            pipeline_path = os.path.join(root, path)
            with open(os.path.join(pipeline_path, "pipeline.toml")) as f:
                pipeline_config = toml.load(f)
                self.add_pipeline(pipeline_config, pipeline_path)


    