from enum import Enum
from ..object import ObjectID

ChunkID = ObjectID

class PositionType(Enum):
    Unknown = 1
    Device = 2
    File = 3
    FileRange = 4
    ChunkManager = 5


class PositionFileRange:
    def __init__(self, path: str, range_begin: int, range_end: int):
        self.path = path
        self.range_begin = range_begin
        self.range_end = range_end

    def encode(self):
        return f"{self.range_begin}:{self.range_end}:{self.path}"

    @staticmethod
    def decode(value: str):
        parts = value.split(":")
        if len(parts) < 3:
            raise ValueError("Invalid input string")

        try:
            range_begin = int(parts[0])
            range_end = int(parts[1])
        except ValueError as e:
            raise ValueError("Invalid range_begin or range_end string") from e

        path = ":".join(parts[2:])
        return PositionFileRange(path, range_begin, range_end)

    def __str__(self):
        return self.encode()

    @staticmethod
    def from_string(value: str):
        return PositionFileRange.decode(value)
