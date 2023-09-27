EC_SUCCESS = 0

EC_UNKNOWN_ERROR = -1

EC_RESET = 1

EC_DECODE_JSON_ERROR = 100


class FunctionError(Exception):
    def __init__(self, code, msg):
        self.code = code
        self.msg = msg
