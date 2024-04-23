# pylint:disable=E0402
from datetime import timedelta, datetime
from typing import Dict

from cachetools import TLRUCache, cached

from ..proto.ai_function import *
from ..environment.sql_database import SQLDatabase, get_from_env


def _my_ttu(_key, _value, now):
    return now + timedelta(seconds=600)


database_cache = TLRUCache(ttu=_my_ttu, maxsize=10000, timer=datetime.now)


@cached(cache=database_cache)
def get_database(uri: str) -> SQLDatabase:
    return SQLDatabase.from_uri(uri)


class GetTableInfosFunction(AIFunction):
    def __init__(self):
        super().__init__()
        self.name = "get_table_infos"
        self.description = "Get table informations in the database"

    def get_id(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "database_url": {"type": "string", "description": "Database URL,Can be set to None"},
            }
        }

    async def execute(self, **kwargs) -> str:
        database_url: str = kwargs.get("database_url")
        if (database_url is None
                or database_url.strip() == ""
                or database_url.strip().lower() == "none"
                or database_url.strip().lower() == "null"):
            database_url = get_from_env(key="database url", env_key="DATABASE_URL")
            if database_url is None:
                return "error: database_url is None"
        database = get_database(database_url)
        tables = database.get_usable_table_names()
        table_infos = database.get_table_info(tables)
        return table_infos

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True

    def is_ready_only(self) -> bool:
        return False


class ExecuteSqlFunction(AIFunction):
    def __init__(self):
        super().__init__()
        self.name = "execute_sql"
        self.description = """
        Input to this function is a detailed and correct SQL query, output is a result from the database.
        If the query is not correct, an error message will be returned.
        If an error is returned, rewrite the query, check the query, and try again.
        """

    def get_id(self) -> str:
        return self.name

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "database_url": {"type": "string", "description": "Database URL,Can be set to None"},
                "sql": {"type": "string", "description": "SQL to execute"}
            }
        }

    async def execute(self, **kwargs) -> str:
        database_url = kwargs.get("database_url")
        if (database_url is None
                or database_url.strip() == ""
                or database_url.strip().lower() == "none"
                or database_url.strip().lower() == "null"):
            database_url = get_from_env(key="database url", env_key="DATABASE_URL")
            if database_url is None:
                return "error: database_url is None"
        sql = kwargs.get("sql")

        database = get_database(database_url)
        return database.run_no_throw(sql)

    def is_local(self) -> bool:
        return True

    def is_in_zone(self) -> bool:
        return True

    def is_ready_only(self) -> bool:
        return False
