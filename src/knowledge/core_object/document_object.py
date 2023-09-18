from ..object import KnowledgeObject, ObjectRelationStore
from ..data import ChunkList, ChunkListWriter
from ..object import ObjectType
from .. import KnowledgeStore

# desc
#   meta
#   hash: "file-hash",
#   tags: {}
# body
#   chunk_list: [chunk_id, chunk_id, ...]


class DocumentObject(KnowledgeObject):
    def __init__(self, meta: dict, tags: dict, chunk_list: ChunkList):
        desc = dict()
        body = dict()
        desc["meta"] = meta
        desc["tags"] = tags
        desc["hash"] = chunk_list.hash.to_base58()
        body["chunk_list"] = chunk_list.chunk_list

        super().__init__(ObjectType.Document, desc, body)

    def get_meta(self):
        return self.desc["meta"]

    def get_tags(self):
        return self.desc["tags"]

    def get_hash(self):
        return self.desc["hash"]

    def get_chunk_list(self):
        return self.body["chunk_list"]


class DocumentObjectBuilder:
    def __init__(self, meta: dict, tags: dict, text: str):
        self.meta = meta
        self.tags = tags
        self.text = text

    def set_meta(self, meta: dict):
        self.meta = meta
        return self

    def set_text(self, text: str):
        self.text = text
        return self

    def build(self, relation_store: ObjectRelationStore) -> DocumentObject:
        chunk_list = KnowledgeStore().get_chunk_list_writer().create_chunk_list_from_text(
            self.text,
            1024 * 4,
            "."
        )
        doc = DocumentObject(self.meta, self.tags, chunk_list)
        doc_id = doc.calculate_id()
        
        # Add relation to store
        for chunk_id in chunk_list.chunk_list:
            relation_store.add_relation(chunk_id, doc_id)
            
        return doc
