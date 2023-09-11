from .chunk import ChunkID, PositionType, PositionFileRange
from .chunk_store import ChunkStore
from .tracker import ChunkTracker
from ..object import HashValue
import logging
from typing import List
import hashlib

class Chunk:
    def __init__(self, file_path: str, range_start: int, size: int = -1):
        self.file_path = file_path
        self.range_start = range_start
        self.size = size

    def read(self):
        with open(self.file_path, 'rb') as f:
            f.seek(self.range_start)
            return f.read(self.size)
        
        

class ChunkReader:
    def __init__(self, chunk_store: ChunkStore, chunk_tracker: ChunkTracker):
        self.chunk_store = chunk_store
        self.chunk_tracker = chunk_tracker

    def get_chunk(self, chunk_id: ChunkID) -> Chunk:
        positions = self.chunk_tracker.get_position(chunk_id)
        if positions is None:
            logging.warning(f"chunk not found: {chunk_id}")
            return None 
       
        if len(positions) == 0:
            logging.warning(f"chunk not found: {chunk_id}")
            return None 

        for pos in positions:
            [position, position_type] = pos
            logging.info(f"chunk position: {chunk_id}, {position}, {position_type}")
            if position_type == PositionType.ChunkStore:
                file_path = self.chunk_store.get_chunk_file_path(chunk_id)
                return Chunk(file_path, 0, -1)
            elif position_type == PositionType.File:
                return Chunk(position, 0, -1)
            elif position_type == PositionType.FileRange:
                file_range = PositionFileRange.decode(position)
                return Chunk(file_range.path, file_range.range_begin, file_range.range_end - file_range.range_begin)
            else:
                raise ValueError(f"invalid position type: {position_type}")

        logging.error(f"chunk not found: {chunk_id}")
        return None
    
    def get_chunk_list(self, chunk_list: List[ChunkID]) -> List[Chunk]:
        return [self.get_chunk(chunk_id) for chunk_id in chunk_list]
        
    def read_chunk_list(self, chunk_ids: List[ChunkID]):
        for chunk_id in chunk_ids:
            chunk = self.get_chunk(chunk_id)
            if chunk is None:
                raise ValueError(f"chunk not found: {chunk_id}")
            
            yield from chunk.read()
    
    def read_text_chunk_list(self, chunk_ids: List[ChunkID]):
        for chunk_id in chunk_ids:
            chunk = self.get_chunk(chunk_id)
            if chunk is None:
                raise ValueError(f"text chunk not found: {chunk_id}")
            
            yield chunk.read().decode("utf-8")
                
    def calc_file_hash(self, file_path: str) -> HashValue:
        hash_obj = hashlib.sha256()
        with open(file_path, "rb") as file:
            while True:
                chunk = file.read(1024 * 1024)
                if not chunk:
                    break
                hash_obj.update(chunk)
        return HashValue(hash_obj.digest())

    def calc_text_hash(self, text: str) -> HashValue:
        hash_obj = hashlib.sha256()
        hash_obj.update(text.encode("utf-8"))