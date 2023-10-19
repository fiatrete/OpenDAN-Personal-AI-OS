# define a knowledge base class
import json
from aios_kernel import ComputeKernel, AIStorage
from knowledge import *


class EmbeddingParser:
    def __init__(self, params: dict):
        self.store = KnowledgeStore()
        self.compute_kernel = ComputeKernel.get_instance()
        self.knowledge_base = KnowledgeBase()
        self._default_text_model = "all-MiniLM-L6-v2"
        self._default_image_model = "clip-ViT-B-32"
        self.vector_store = ChromaVectorStore(AIStorage().get_myai_dir() / "knowledge", self._default_text_model)

    def __get_vector_store(self, model_name: str) -> ChromaVectorStore:
        return ChromaVectorStore(AIStorage().get_myai_dir() / "knowledge", self._default_text_model)

    async def __embedding_document(self, document: DocumentObject):
        for chunk_id in document.get_chunk_list():
            chunk = self.knowledge_base.store.get_chunk_reader().get_chunk(chunk_id)
            if chunk is None:
                raise ValueError(f"text chunk not found: {chunk_id}")
        
            text = chunk.read().decode("utf-8")
            vector = await self.compute_kernel.do_text_embedding(text, self._default_text_model)
            if vector:
                await self.get_vector_store(self._default_text_model).insert(vector, chunk_id)

    async def __embedding_image(self, image: ImageObject):
        # desc = {}
        # if not not image.get_meta():
        #     desc["meta"] = image.get_meta()
        # if not not image.get_exif():
        #     desc["exif"] = image.get_exif()
        # if not not image.get_tags():
        #     desc["tags"] = image.get_tags()
        # vector = await self.compute_kernel.do_text_embedding(json.dumps(desc), self._default_text_model)
        vector = await self.compute_kernel.do_image_embedding(image.calculate_id(), self._default_image_model)
        if vector:
            await self.get_vector_store(self._default_image_model).insert(vector, image.calculate_id())

    async def __embedding_video(self, vedio: VideoObject):
        desc = {}
        if not not vedio.get_meta():
            desc["meta"] = vedio.get_meta()
        if not not vedio.get_info():
            desc["info"] = vedio.get_info()
        if not not vedio.get_tags():
            desc["tags"] = vedio.get_tags()
        vector = await self.compute_kernel.do_text_embedding(json.dumps(desc), self._default_text_model)
        await self.get_vector_store(self._default_text_model).insert(vector, vedio.calculate_id())

    async def __embedding_rich_text(self, rich_text: RichTextObject):
        for document_id in rich_text.get_documents().values():
            document = DocumentObject.decode(self.store.get_object_store().get_object(document_id))
            await self.__embedding_document(document)
        for image_id in rich_text.get_images().values():
            image = ImageObject.decode(self.store.get_object_store().get_object(image_id))
            await self.__embedding_image(image)
        for video_id in rich_text.get_videos().values():
            video = VideoObject.decode(self.store.get_object_store().get_object(video_id))
            await self.__embedding_video(video)
        for rich_text_id in rich_text.get_rich_texts().values():
            rich_text = RichTextObject.decode(self.store.get_object_store().get_object(rich_text_id))
            await self.__embedding_rich_text(rich_text)

    async def __embedding_email(self, email: EmailObject):
        vector = await self.compute_kernel.do_text_embedding(json.dumps(email.get_desc()), self._default_text_model)
        await self.get_vector_store(self._default_text_model).insert(vector, email.calculate_id())
        await self.__embedding_rich_text(email.get_rich_text())


    async def __do_embedding(self, object: KnowledgeObject):
        if object.get_object_type() == ObjectType.Document:
            await self.__embedding_document(object)
        if object.get_object_type() == ObjectType.Image:
            await self.__embedding_image(object)
        if object.get_object_type() == ObjectType.Video:
            await self.__embedding_video(object)
        if object.get_object_type() == ObjectType.RichText:
            await self.__embedding_rich_text(object)
        if object.get_object_type() == ObjectType.Email:
            await self.__embedding_email(object)
        else:
            pass
    
    async def parse(self, object: ObjectID):
        obj = self.knowledge_base.load_object(object)
        await self.__do_embedding(obj)

def init(params: dict) -> EmbeddingParser:
    return EmbeddingParser(params)