# define a object type enum
from abc import ABC, abstractmethod
from enum import Enum
from .hash import HashValue
import base58
import base36


class ObjectType(Enum):
    Chunk = 7
    TextChunk = 100
    Image = 101
    Email = 102


# define a object ID class to identify a object
class ObjectID:  # pylint: disable=too-few-public-methods
    def __init__(self, object_type: ObjectType, value: bytes):
        assert len(value) == 32, "ObjectID must be 32 bytes long"
        self.object_type = object_type
        self.value = value

    def __str__(self):
        return self.to_base58()

    def get_object_type(self):
        return self.object_type
    
    def to_base58(self):
        return base58.b58encode(self.value).decode()

    @staticmethod
    def from_base58(s):
        return ObjectID(base58.b58decode(s))

    def to_base36(self):
        # Convert the bytes to int before encoding
        num = int.from_bytes(self.value, "big")
        return base36.dumps(num)

    @staticmethod
    def from_base36(s):
        # Decode to int and then convert to bytes
        num = base36.loads(s)
        return ObjectID(num.to_bytes((num.bit_length() + 7) // 8, "big"))

    @staticmethod
    def new_chunk_id(chunk_hash: HashValue):
        return ObjectID(ObjectType.Chunk, chunk_hash.value)
    
    @staticmethod
    def hash_data(data: bytes):
        return ObjectID.new_chunk_id(HashValue.hash_data(data))