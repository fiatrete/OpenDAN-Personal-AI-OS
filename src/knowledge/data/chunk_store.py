import os
import logging
from ..object import FileBlobStorage
from .chunk import ChunkID


class ChunkStore:
    def __init__(self, root_dir: str):
        logging.info(f"will init chunk store, root_dir={root_dir}")

        if not os.path.exists(root_dir):
            os.makedirs(root_dir)
            
        self.root = root_dir
        self.blob = FileBlobStorage(root_dir)

    def put_chunk(self, chunk_id: ChunkID, contents: bytes):
        self.blob.put(chunk_id, contents)

    def get_chunk(self, chunk_id: ChunkID) -> bytes:
        return self.blob.get(chunk_id)

    def delete_chunk(self, chunk_id: ChunkID):
        self.blob.delete(chunk_id)
      
    def get_chunk_file_path(self, chunk_id: ChunkID) -> str:
        return self.blob.get_full_path(chunk_id, False)
    