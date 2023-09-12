from .vector_base import VectorBase
from ..object import ObjectID
import chromadb
import logging
import os


class ChromaVectorStore(VectorBase):
    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)

        logging.info(
            "will init chroma vector store, model={}".format(model_name)
        )

        directory = os.path.join(
            os.path.dirname(__file__), "../../../rootfs/data/vector"
        )
        logging.info("will use vector store: {}".format(directory))

        client = chromadb.PersistentClient(
            path=directory, settings=chromadb.Settings(anonymized_telemetry=False)
        )
        # client = chromadb.Client()

        collection_name = "coll_{}".format(model_name)
        logging.info("will init chroma colletion: %s", collection_name)

        collection = client.get_or_create_collection(collection_name)
        self.collection = collection

    async def insert(self, vector: [float], id: ObjectID):
        self.collection.add(
            embeddings=vector,
            ids=id,
        )

    async def query(self, vector: [float], top_k: int) -> [ObjectID]:
        ret = self.collection.query(
            query_embeddings=vector,
            n_results=top_k,
        )

        return ret["ids"]

    async def delete(self, id: ObjectID):
        self.collection.delete(
            ids=id,
        )
