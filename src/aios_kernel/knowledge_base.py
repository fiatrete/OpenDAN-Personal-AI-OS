# define a knowledge base class
import json
from . import AgentPrompt, ComputeKernel
from ..knowledge import *


class KnowledgeBase:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.__singleton_init__()

        return cls._instance

    def __singleton_init__(self) -> None:
        self.store = KnowledgeStore()
        self.compute_kernel = ComputeKernel()

    async def __embedding_document(self, document: DocumentObject):
        for chunk_id in document.get_chunk_list():
            chunk = self.store.get_chunk_reader().get_chunk(chunk_id)
            if chunk is None:
                raise ValueError(f"text chunk not found: {chunk_id}")
        
            text = chunk.read().decode("utf-8")
            vector = await self.compute_kernel.do_text_embedding(text)
            self.store.get_vector_store("default").insert(vector, chunk_id)

    async def __embedding_image(self, image: ImageObject):
        desc = {}
        if not image.get_meta():
            desc["meta"] = image.get_meta()
        if not image.get_exif():
            desc["exif"] = image.get_exif()
        if not image.get_tags():
            desc["tags"] = image.get_tags()
        vector = await self.compute_kernel.do_text_embedding(json.dumps(desc))
        self.store.get_vector_store("default").insert(vector, image.calculate_id())

    async def __embedding_vedio(self, vedio: VideoObject):
        desc = {}
        if not vedio.get_meta():
            desc["meta"] = vedio.get_meta()
        if not vedio.get_info():
            desc["info"] = vedio.get_info()
        if not vedio.get_tags():
            desc["tags"] = vedio.get_tags()
        vector = await self.compute_kernel.do_text_embedding(json.dumps(desc))
        self.store.get_vector_store("default").insert(vector, vedio.calculate_id())

    async def __embedding_rich_text(self, rich_text: RichTextObject):
        for document in rich_text.get_documents().values():
            await self.__embedding_document(document)
        for image in rich_text.get_images().values():
            await self.__embedding_image(image)
        for vedio in rich_text.get_videos().values():
            await self.__embedding_vedio(vedio)
        for rich_text in rich_text.get_rich_texts().values():
            await self.__embedding_rich_text(rich_text)

    async def __embedding_email(self, email: EmailObject):
        vector = await self.compute_kernel.do_text_embedding(json.dumps(email.get_desc()))
        self.store.get_vector_store("default").insert(vector, email.calculate_id())
        await self.__embedding_rich_text(email.get_rich_text())

    async def do_embedding(self, object: KnowledgeObject):
        if object.get_object_type() == ObjectType.Document:
            await self.__embedding_document(object)
        if object.get_object_type() == ObjectType.Image:
            await self.__embedding_image(object)
        if object.get_object_type() == ObjectType.Video:
            await self.__embedding_vedio(object)
        if object.get_object_type() == ObjectType.RichText:
            await self.__embedding_rich_text(object)
        if object.get_object_type() == ObjectType.Email:
            await self.__embedding_email(object)
        else:
            pass

    async def query(self, prompt: AgentPrompt) -> [ObjectID]:
        results = []
        for msg in prompt.messages:
            if msg.role == "user":
                vector = await self.compute_kernel.do_text_embedding(msg.content)
                object_ids = self.store.get_vector_store("default").query(vector, 10)
                results.append(object_ids)
        return results



                        
                    
                

    