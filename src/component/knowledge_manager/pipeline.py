import os
import runpy
import toml
import asyncio
from knowledge import KnowledgePipelineEnvironment, KnowledgePipeline

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
        from .parser import embedding
        self.register_parser("embedding", embedding.init)

    def register_input(self, name: str, init_method):
        self.input_modules[name] = init_method
        
    def register_parser(self, name: str, parser_method):
        self.parser_modules[name] = parser_method

    def add_pipeline(self, config: dict, path: str):
        name = config["name"]
        if name in self.pipelines["names"]:
            return
        
        input_module = config["input"]["module"]
        _, ext = os.path.splitext(input_module)
        if ext == ".py":
            input_module = os.path.abspath(path, input_module)
            input_init = runpy.run_path(input_module)["init"]
        else:
            input_init = self.input_modules.get(input_module)
        input_params = config["input"]["params"]

        parser_module = config["parser"]["module"]
        _, ext = os.path.splitext(parser_module)
        if ext == ".py":
            parser_module = os.path.abspath(path, parser_module)
            parser_init = runpy.run_path(parser_module)["init"]
        else:
            parser_init = self.parser_modules.get(parser_module)
        parser_params = config["parser"]["params"]


        data_path = os.path.join(self.root_dir, name)
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
        if not os.path.exists(config_path):
            return 
        with open(config_path, "r") as f:
            config = toml.load(f)
        for path in config["pipelines"]:
            pipeline_path = os.path.join(root, path)
            with open(os.path.join(pipeline_path, "pipeline.toml")) as f:
                pipeline_config = toml.load(f)
                self.add_pipeline(pipeline_config, pipeline_path)
