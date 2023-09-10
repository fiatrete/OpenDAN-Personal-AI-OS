import os
import hashlib
import re
from typing import Tuple, List
from .chunk_store import ChunkStore
from .chunk import ChunkID, PositionFileRange, PositionType
from ..object import HashValue
from .tracker import ChunkTracker
from .chunk_list import ChunkList

class ChunkListWriter:
    def __init__(self, chunk_store: ChunkStore, chunk_tracker: ChunkTracker):
        self.chunk_store = chunk_store
        self.chunk_tracker = chunk_tracker

    def create_chunk_list_from_file(
        self, file_path: str, chunk_size: int, restore: bool
    ) -> ChunkList:
        assert (
            chunk_size % (1024 * 1024) == 0
        ), "chunk size should be an integral multiple of 1MB"
        chunk_list = []
        hash_obj = hashlib.sha256()

        with open(file_path, "rb") as file:
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                chunk_id = ChunkID.hash_data(chunk)
                chunk_list.append(chunk_id)

                hash_obj.update(chunk)

                if restore:
                    self.chunk_tracker.add_position(
                        chunk_id, file_path, PositionType.ChunkStore
                    )
                    self.chunk_store.put_chunk(chunk_id, chunk)
                else:
                    file_range = PositionFileRange(
                        file_path, file.tell() - chunk_size, chunk_size
                    )
                    self.chunk_tracker.add_position(
                        chunk_id, file_range, PositionType.FileRange
                    )

        file_hash = HashValue(hash_obj.digest())
        print(f"calc file hash: {file_path}, {file_hash}")
        
        return ChunkList(chunk_list, file_hash)

    def create_chunk_list_from_text(
        self, text: str, chunk_max_words: int, separator_chars: str = ".,"
    ) -> Tuple[List[ChunkID], HashValue]:
        text_list = self._split_text_list(text, chunk_max_words, separator_chars)
        chunk_list = []
        hash_obj = hashlib.sha256()

        for text in text_list:
            chunk_bytes = text.encode("utf-8")
            hash_obj.update(chunk_bytes)

            chunk_id = ChunkID.hash_data(chunk_bytes)
            chunk_list.append(chunk_id)
            self.chunk_tracker.add_position(chunk_id, "", PositionType.ChunkStore)
            self.chunk_store.put_chunk(chunk_id, chunk_bytes)

        hash = HashValue(hash_obj.digest())
        return ChunkList(chunk_list, hash)

    @staticmethod
    def _split_text_list(
        text: str, chunk_max_words: int, separator_chars: str = ".,"
    ) -> List[str]:
        sentences = re.split(f"[{separator_chars}]", text)
        chunk_list = []
        chunk = []
        word_count = 0
        for sentence in sentences:
            words = sentence.split()
            for word in words:
                if word_count < chunk_max_words:
                    chunk.append(word)
                    word_count += 1
                else:
                    chunk_list.append(" ".join(chunk))
                    chunk = [word]
                    word_count = 1
        if chunk:
            chunk_list.append(" ".join(chunk))
        return chunk_list