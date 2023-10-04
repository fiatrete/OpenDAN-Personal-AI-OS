from ..object import HashValue
from .chunk import ChunkID
from typing import List

class ChunkList:
    def __init__(self, chunk_list: List[ChunkID], hash: HashValue):
        self.chunk_list = chunk_list
        self.hash = hash

    def __str__(self):
        return self.hash.to_base58()

    def __repr__(self):
        return f"chunk_list: {self.chunk_list}, hash: {self.hash}"