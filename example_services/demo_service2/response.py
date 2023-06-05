from typing import Union, Tuple, Dict, List
from pydantic import BaseModel


class Response(BaseModel):
    code: int
    message: str
    data: Union[Dict, List]


def build_success_response(data: Union[Dict, List]):
    return {
        "code": RESPONSE_SUCCESS[0],
        "message": RESPONSE_SUCCESS[1],
        "data": data
    }


def build_failure_response(result_tuple: Tuple, data: Union[Dict, List]):
    return build_failure_response(result_tuple[0], result_tuple[1], data)


def build_failure_response(code: int, message: str, data: Union[Dict, List]):
    return {
        "code": code,
        "message": message,
        "data": data
    }


RESPONSE_SUCCESS = 200, "SUCCESS"
RESPONSE_UNKNOWN_ERROR = 100001, "UNKNOWN ERROR"
RESPONSE_UNAUTHORIZED = 100002, "UNAUTHORIZED"
RESPONSE_TASK_NOT_FOUND = 100003, "TASK NOT FOUND"
