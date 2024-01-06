# pylint:disable=E0402
import json
from typing import Dict

from ..proto.ai_function import *
from ..agent.llm_context import GlobaToolsLibrary
from duckduckgo_search import AsyncDDGS


class DuckDuckGoTextSearchFunction(AIFunction):
    def __init__(self):
        self.name = "web.search.duckduckgo"
        self.description = "Search web by text (powered by DuckDuckGo)"
        self.region = "wt-wt"
        self.safesearch = "moderate"
        self.time = "y"
        self.max_results = 5
        self.parameters = ParameterDefine.create_parameters({
            "query": {"type": "string", "description": "The query to search for."}
        })

    def register_function(self):
        GlobaToolsLibrary.get_instance().register_tool_function(self)

    def get_id(self) -> str:
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

            return json.dumps(results,,ensure_ascii=False)

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True

    def is_ready_only(self) -> bool:
        return False
