import json
from typing import Dict

from ..agent.ai_function import AIFunction
from duckduckgo_search import AsyncDDGS


class DuckDuckGoTextSearchFunction(AIFunction):
    def __init__(self):
        self.name = "duckduckgo_text_search"
        self.description = "Search text from duckduckgo.com"
        self.region = "wt-wt"
        self.safesearch = "moderate"
        self.time = "y"
        self.max_results = 5

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict:
        return {"type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The query to search for."}
                }
                }

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
