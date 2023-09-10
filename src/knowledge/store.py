import os
from .object import ObjectStore
from .data import ChunkStore, ChunkTracker
import logging


# KnowledgeStore class, 聚合ChunkStore，ChunkTracker， ObjectStore，并且是一个全局单例，可以方便的使用这三个内置的store示例
class KnowledgeStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            directory = os.path.join(
                os.path.dirname(__file__), "../../rootfs/data/"
            )
            directory = os.path.normpath(directory)
            print(directory)

            if not os.path.exists(directory):
                os.makedirs(directory)

            cls._instance.__singleton_init__(directory)

        return cls._instance

    def __singleton_init__(self, root_dir: str):
        logging.info(f"will init knowledge store, root_dir={root_dir}")

        self.root = root_dir

        object_store_dir = os.path.join(root_dir, "object")
        self.object_store = ObjectStore(object_store_dir)

        chunk_store_dir = os.path.join(root_dir, "chunk")
        self.chunk_store = ChunkStore(chunk_store_dir)
        self.chunk_tracker = ChunkTracker(chunk_store_dir)

    def get_object_store(self) -> ObjectStore:
        return self.object_store

    def get_chunk_store(self) -> ChunkStore:
        return self.chunk_store

    def get_chunk_tracker(self) -> ChunkTracker:
        return self.chunk_tracker
