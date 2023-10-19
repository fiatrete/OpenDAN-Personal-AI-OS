import os

from .object import ObjectStore, ObjectRelationStore, ObjectID, ObjectType, KnowledgeObject, DocumentObject, ImageObject, VideoObject, RichTextObject, EmailObject
from core_object import DocumentObject, ImageObject, VideoObject, RichTextObject, EmailObject
from .data import ChunkStore, ChunkTracker, ChunkListWriter, ChunkReader
import json
import logging




# KnowledgeStore class, which aggregates ChunkStore, ChunkTracker, and ObjectStore, and is a global singleton that makes it easy to use these three built-in store examples
class KnowledgeStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            
            import aios_kernel
            knowledge_dir = aios_kernel.storage.AIStorage().get_myai_dir() / "knowledge" / "objects"

            if not os.path.exists(knowledge_dir):
                os.makedirs(knowledge_dir)

            cls._instance.__singleton_init__(knowledge_dir)

        return cls._instance

    def __singleton_init__(self, root_dir: str):
        logging.info(f"will init knowledge store, root_dir={root_dir}")

        self.root = root_dir

        relation_store_dir = os.path.join(root_dir, "relation")
        self.relation_store = ObjectRelationStore(relation_store_dir)

        object_store_dir = os.path.join(root_dir, "object")
        self.object_store = ObjectStore(object_store_dir)

        chunk_store_dir = os.path.join(root_dir, "chunk")
        self.chunk_store = ChunkStore(chunk_store_dir)
        self.chunk_tracker = ChunkTracker(chunk_store_dir)
        self.chunk_list_writer = ChunkListWriter(self.chunk_store, self.chunk_tracker)
        self.chunk_reader = ChunkReader(self.chunk_store, self.chunk_tracker)

    
    def get_relation_store(self) -> ObjectRelationStore:
        return self.relation_store

    def get_object_store(self) -> ObjectStore:
        return self.object_store

    def get_chunk_store(self) -> ChunkStore:
        return self.chunk_store

    def get_chunk_tracker(self) -> ChunkTracker:
        return self.chunk_tracker
    
    def get_chunk_list_writer(self) -> ChunkListWriter:
        return self.chunk_list_writer
    
    def get_chunk_reader(self) -> ChunkReader:
        return self.chunk_reader
    
    async def insert_object(self, object: KnowledgeObject):
        self.object_store.put_object(object.calculate_id(), object.encode())
    
    def load_object(self, object_id: ObjectID) -> KnowledgeObject:
        if object_id.get_object_type() == ObjectType.Document:
            return DocumentObject.decode(self.store.get_object_store().get_object(object_id))
        if object_id.get_object_type() == ObjectType.Image:
            return ImageObject.decode(self.store.get_object_store().get_object(object_id))
        if object_id.get_object_type() == ObjectType.Video:
            return VideoObject.decode(self.store.get_object_store().get_object(object_id))
        if object_id.get_object_type() == ObjectType.RichText:
            return RichTextObject.decode(self.store.get_object_store().get_object(object_id))
        if object_id.get_object_type() == ObjectType.Email:
            return EmailObject.decode(self.store.get_object_store().get_object(object_id))
        else:
            pass
    
    def parse_object_in_message(self, message: str) -> KnowledgeObject:
        # get message's first line 
        logging.info(f"tg parse resp message: {message}")
        lines = message.split("\n")
        if len(lines) > 0:
            message = lines[0]
            try:
                desc = json.loads(message)
                if isinstance(desc, dict):
                    object_id = desc["id"]
                else:
                    object_id = desc[0]["id"]
            except Exception as e:
                return None
            
            if object_id is not None:
                return self.load_object(ObjectID.from_base58(object_id))
            
            
    def bytes_from_object(self, object: KnowledgeObject) -> bytes:
        if object.get_object_type() == ObjectType.Image:
            image_object = object
            return self.get_chunk_reader().read_chunk_list_to_single_bytes(image_object.get_chunk_list())