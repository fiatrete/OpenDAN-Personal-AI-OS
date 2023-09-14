# define a knowledge base class
import json
import pickle
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
        if not not image.get_meta():
            desc["meta"] = image.get_meta()
        if not not image.get_exif():
            desc["exif"] = image.get_exif()
        if not not image.get_tags():
            desc["tags"] = image.get_tags()
        vector = await self.compute_kernel.do_text_embedding(json.dumps(desc))
        self.store.get_vector_store("default").insert(vector, image.calculate_id())

    async def __embedding_video(self, vedio: VideoObject):
        desc = {}
        if not not vedio.get_meta():
            desc["meta"] = vedio.get_meta()
        if not not vedio.get_info():
            desc["info"] = vedio.get_info()
        if not not vedio.get_tags():
            desc["tags"] = vedio.get_tags()
        vector = await self.compute_kernel.do_text_embedding(json.dumps(desc))
        self.store.get_vector_store("default").insert(vector, vedio.calculate_id())

    async def __embedding_rich_text(self, rich_text: RichTextObject):
        for document in rich_text.get_documents().values():
            await self.__embedding_document(document)
        for image in rich_text.get_images().values():
            await self.__embedding_image(image)
        for vedio in rich_text.get_videos().values():
            await self.__embedding_video(vedio)
        for rich_text in rich_text.get_rich_texts().values():
            await self.__embedding_rich_text(rich_text)

    async def __embedding_email(self, email: EmailObject):
        vector = await self.compute_kernel.do_text_embedding(json.dumps(email.get_desc()))
        self.store.get_vector_store("default").insert(vector, email.calculate_id())
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

    def __save_document(self, document: DocumentObject):
        doc_id = document.calculate_id()
        self.store.get_object_store().put_object(doc_id, document.encode())
        for chunk_id in document.get_chunk_list():
            self.store.get_relation_store().add_relation(chunk_id, doc_id)

    def __save_image(self, image: ImageObject):
        image_id = image.calculate_id()
        self.store.get_object_store().put_object(image_id, image.encode())

    def __save_video(self, video: VideoObject):
        video_id = video.calculate_id()
        self.store.get_object_store().put_object(video_id, video.encode())

    def __save_rich_text(self, rich_text: RichTextObject):
        rich_text_id = rich_text.calculate_id()
        # rich_text_enc = dict()
        # rich_text_enc["desc"] = rich_text.desc
        # rich_text_enc["body"] = {"documents": {}, "images": {}, "videos": {}, "rich_texts": {}}
        for key, document in rich_text.get_documents().items():
            self.__save_document(document)
            doc_id = document.calculate_id()
            self.store.get_relation_store().add_relation(doc_id, rich_text_id)
            # rich_text_enc["body"]["documents"][key] = doc_id
        for key, image in rich_text.get_images().items():
            self.__save_image(image)
            image_id = image.calculate_id()
            self.store.get_relation_store().add_relation(image_id, rich_text_id)
            # rich_text_enc["body"]["images"][key] = image_id
        for key, video in rich_text.get_videos().items():
            self.__save_video(video)
            video_id = video.calculate_id()
            self.store.get_relation_store().add_relation(video_id, rich_text_id)
            # rich_text_enc["body"]["videos"][key] = video_id
        for key, rich_text in rich_text.get_rich_texts().items():
            self.__save_rich_text(rich_text)
            rich_text_id = rich_text.calculate_id()
            self.store.get_relation_store().add_relation(rich_text_id, rich_text_id)
            # rich_text_enc["body"]["rich_texts"][key] = rich_text_id


        self.store.get_object_store().put_object(rich_text_id, rich_text.encode())

    def __save_email(self, email: EmailObject):
        email_id = email.calculate_id()
        # email_enc = dict()
        # email_enc["desc"] = email.desc
        # email_enc["body"] = {"content": None}
        self.__save_rich_text(email.get_rich_text())
        rich_text_id = email.get_rich_text().calculate_id()
        self.store.get_relation_store().add_relation(rich_text_id, email_id)
        # email_enc["body"]["content"] = rich_text_id
        self.store.get_object_store().put_object(email_id, email.encode())

    
    def __save_object(self, object: KnowledgeObject):
        if object.get_object_type() == ObjectType.Document:
            self.__save_document(object)
        if object.get_object_type() == ObjectType.Image:
            self.__save_image(object)
        if object.get_object_type() == ObjectType.Video:
            self.__save_video(object)
        if object.get_object_type() == ObjectType.RichText:
            self.__save_rich_text(object)
        if object.get_object_type() == ObjectType.Email:
            self.__save_email(object)
        else:
            pass

    async def insert_object(self, object: KnowledgeObject):
        self.__save_object(object)
        self.__do_embedding(object)

    async def query_objects(self, prompt: AgentPrompt) -> [ObjectID]:
        results = []
        for msg in prompt.messages:
            if msg.role == "user":
                vector = await self.compute_kernel.do_text_embedding(msg.content)
                object_ids = self.store.get_vector_store("default").query(vector, 10)
                results.append(object_ids)
        return results

    async def __load_object(self, object_id: ObjectID) -> KnowledgeObject:
        if object_id.get_object_type() == ObjectType.Document:
            return DocumentObject.decode(self.store.get_object_store().get_object(object_id))
        object = self.store.get_object_store().get_object(object_id)
        

    async def __prompt_from_objects(self, object_ids: [ObjectID]) -> AgentPrompt:
        prompt = AgentPrompt()
        for object_id in object_ids:
            object = self.store.get_object_reader().get_object(object_id)
            if object is None:
                raise ValueError(f"object not found: {object_id}")
            if object.get_object_type() == ObjectType.Document:
                document = object
                prompt.messages.append({"role": "agent", "content": document.get_body()})
            if object.get_object_type() == ObjectType.Image:
                image = object
                prompt.messages.append({"role": "agent", "content": json.dumps(image.get_desc())})
            if object.get_object_type() == ObjectType.Video:
                video = object
                prompt.messages.append({"role": "agent", "content": json.dumps(video.get_desc())})
            if object.get_object_type() == ObjectType.RichText:
                rich_text = object
                prompt.messages.append({"role": "agent", "content": json.dumps(rich_text.get_desc())})
            if object.get_object_type() == ObjectType.Email:
                email = object
                prompt.messages.append({"role": "agent", "content": json.dumps(email.get_desc())})
        return prompt

                        
                    
                

    