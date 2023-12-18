# pylint:disable=E0402
import json
from typing import Dict

from ..proto.ai_function import *
from ..agent.llm_context import GlobaToolsLibrary
from duckduckgo_search import AsyncDDGS


class DuckDuckGoTextSearchFunction(AIFunction):
    def __init__(self):
        self.name = "duckduckgo_text_search"
        self.description = "Search text from duckduckgo.com"
        self.region = "wt-wt"
        self.safesearch = "moderate"
        self.time = "y"
        self.max_results = 5
        self.parameters = ParameterDefine.create_parameters({
            "query": {"type": "string", "description": "The query to search for."}
        })

    def register_function(self):
        GlobaToolsLibrary.get_instance().register_tool_function(self)

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict:
        return self.parameters 

    async def execute(self, **kwargs) -> str:
        query = kwargs.get("query")

        async with AsyncDDGS() as ddgs:
            results = [r async for r in ddgs.text(
                query,
                region=self.region,
                safesearch=self.safesearch,
                timelimit=self.time,
                backend="api",
                max_results=self.max_results
            )]

            return json.dumps(results)

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True

    def is_ready_only(self) -> bool:
        return False
