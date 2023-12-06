# define a object type enum
from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum

from .object_id import ObjectID, ObjectType
import hashlib
import json
import pickle
from typing import Any


class ObjectEnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, ObjectID):
            return o.to_base58()

        return super().default(o)


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
    
    def get_summary(self) -> str:
        return self.desc.get("summary")
    
    # def get_articl_catelog(self) -> str:
    #     assert self.object_type == ObjectType.Document
    #     return self.desc.get("catelog")
    
    # def get_article_full_content(self) -> str:
    #     assert self.object_type == ObjectType.Document
    #     return self.body

    def calculate_id(self):
        # Convert the object_type and desc to string and compute the SHA256 hash
        data = json.dumps(
            {"object_type": self.object_type, "desc": self.desc},
            cls=ObjectEnhancedJSONEncoder,
        )
        sha256 = hashlib.sha256()
        sha256.update(data.encode())
        hash_bytes = sha256.digest()
        return ObjectID(bytes([self.object_type]) + hash_bytes[1:])

    def encode(self) -> bytes:
        return pickle.dumps(self)

    @staticmethod
    def decode(data: bytes) -> "KnowledgeObject":
        return pickle.loads(data)
