# define a object type enum
from abc import ABC, abstractmethod
from enum import IntEnum
from .hash import HashValue
import base58
import base36


class ObjectType(IntEnum):
    Chunk = 7
    Image = 101
    Video = 102
    Document = 103
    RichText = 104
    Email = 105
    UserDef = 200

    def is_user_def(self) -> bool:
        return self.value >= 200
    
    def get_user_def_type_code(self):
        return (self.value - 200) if self.is_user_def() else None
    
    @classmethod
    def from_user_def_type_code(value):
        return value + 200


# define a object ID class to identify a object
class ObjectID:  # pylint: disable=too-few-public-methods
    def __init__(self, value: bytes):
        assert len(value) == 32, "ObjectID must be 32 bytes long"
        self.value = value

    def __str__(self):
        return self.to_base58()
    
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
        assert len(chunk_hash.value) == 32, "ObjectID must be 32 bytes long"
        return ObjectID(bytes([ObjectType.Chunk]) + chunk_hash.value[1:])
    
    def get_object_type(self) -> ObjectType:
        return ObjectType(self.value[0])
    
    @staticmethod
    def hash_data(data: bytes):
        return ObjectID.new_chunk_id(HashValue.hash_data(data))
    
    def __eq__(self, other) -> bool:
        return self.value == other.value