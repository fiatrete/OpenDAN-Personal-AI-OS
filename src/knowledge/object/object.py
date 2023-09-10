
# define a object type enum
from abc import ABC, abstractmethod
from enum import Enum
from .object_id import ObjectID, ObjectType
import hashlib
import json
import pickle

class KnowledgeObject(ABC):
    def __init__(self, object_type: ObjectType, desc: dict = {}, body: dict = {}):
        self.desc = desc
        self.body = body
        self.object_type = object_type

    def get_object_type(self) -> ObjectType:
        return self.object_type

    def object_id(self) -> ObjectID:
        return self.calculate_id()
    
    def set_desc_with_key_value(self, key, value):
        self.desc[key] = value

    def get_desc_with_key(self, key):
        return self.desc.get(key)

    def get_desc(self) -> dict:
        return self.desc
    
    def set_body_with_key_value(self, key, value):
        self.body[key] = value

    def get_body_with_key(self, key):
        return self.body.get(key)

    def get_body(self) -> dict:
        return self.body
    
    def calculate_id(self):
        # Convert the object_type and desc to string and compute the SHA256 hash
        data = json.dumps({"object_type": self.object_type, "desc": self.desc})
        sha256 = hashlib.sha256()
        sha256.update(data.encode())
        return ObjectID(sha256.digest())

    def encode(self) -> bytes:
        return pickle.dumps(self)

    @staticmethod
    def decode(data: bytes):
        return pickle.loads(data)

    
