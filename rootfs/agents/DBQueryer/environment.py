from typing import Optional

from aios.environment.environment import Environment
from aios.environment.sql_database_function import GetTableInfosFunction, ExecuteSqlFunction


class DBQuerierEnvironment(Environment):
    def __init__(self):
        super().__init__("fairy")
        self.add_ai_function(GetTableInfosFunction())
        self.add_ai_function(ExecuteSqlFunction())

    def _do_get_value(self, key: str) -> Optional[str]:
        pass


def init():
    return DBQuerierEnvironment()
