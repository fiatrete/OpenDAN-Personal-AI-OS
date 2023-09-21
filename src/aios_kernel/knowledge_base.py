# define a knowledge base class
import json
import logging
from .agent import AgentPrompt
from .compute_kernel import ComputeKernel 
from .storage import AIStorage
from knowledge import *


class KnowledgeBase:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.__singleton_init__()

        return cls._instance

    def __singleton_init__(self) -> None:
        self.store = KnowledgeStore()
        self.compute_kernel = ComputeKernel.get_instance()

    async def __embedding_document(self, document: DocumentObject):
        for chunk_id in document.get_chunk_list():
            chunk = self.store.get_chunk_reader().get_chunk(chunk_id)
            if chunk is None:
                raise ValueError(f"text chunk not found: {chunk_id}")
        
            text = chunk.read().decode("utf-8")
            vector = await self.compute_kernel.do_text_embedding(text)
            await self.store.get_vector_store("default").insert(vector, chunk_id)

    async def __embedding_image(self, image: ImageObject):
        desc = {}
        if not not image.get_meta():
            desc["meta"] = image.get_meta()
        if not not image.get_exif():
            desc["exif"] = image.get_exif()
        if not not image.get_tags():
            desc["tags"] = image.get_tags()
        vector = await self.compute_kernel.do_text_embedding(json.dumps(desc))
        await self.store.get_vector_store("default").insert(vector, image.calculate_id())

    async def __embedding_video(self, vedio: VideoObject):
        desc = {}
        if not not vedio.get_meta():
            desc["meta"] = vedio.get_meta()
        if not not vedio.get_info():
            desc["info"] = vedio.get_info()
        if not not vedio.get_tags():
            desc["tags"] = vedio.get_tags()
        vector = await self.compute_kernel.do_text_embedding(json.dumps(desc))
        await self.store.get_vector_store("default").insert(vector, vedio.calculate_id())

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
        vector = await self.compute_kernel.do_text_embedding(json.dumps(email.get_desc()))
        await self.store.get_vector_store("default").insert(vector, email.calculate_id())
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

    # def __save_document(self, document: DocumentObject):
    #     doc_id = document.calculate_id()
    #     self.store.get_object_store().put_object(doc_id, document.encode())
    #     for chunk_id in document.get_chunk_list():
    #         self.store.get_relation_store().add_relation(chunk_id, doc_id)

    # def __save_image(self, image: ImageObject):
    #     image_id = image.calculate_id()
    #     self.store.get_object_store().put_object(image_id, image.encode())

    # def __save_video(self, video: VideoObject):
    #     video_id = video.calculate_id()
    #     self.store.get_object_store().put_object(video_id, video.encode())

    # def __save_rich_text(self, rich_text: RichTextObject):
    #     rich_text_id = rich_text.calculate_id()
    #     # rich_text_enc = dict()
    #     # rich_text_enc["desc"] = rich_text.desc
    #     # rich_text_enc["body"] = {"documents": {}, "images": {}, "videos": {}, "rich_texts": {}}
    #     for key, document in rich_text.get_documents().items():
    #         self.__save_document(document)
    #         doc_id = document.calculate_id()
    #         self.store.get_relation_store().add_relation(doc_id, rich_text_id)
    #         # rich_text_enc["body"]["documents"][key] = doc_id
    #     for key, image in rich_text.get_images().items():
    #         self.__save_image(image)
    #         image_id = image.calculate_id()
    #         self.store.get_relation_store().add_relation(image_id, rich_text_id)
    #         # rich_text_enc["body"]["images"][key] = image_id
    #     for key, video in rich_text.get_videos().items():
    #         self.__save_video(video)
    #         video_id = video.calculate_id()
    #         self.store.get_relation_store().add_relation(video_id, rich_text_id)
    #         # rich_text_enc["body"]["videos"][key] = video_id
    #     for key, rich_text in rich_text.get_rich_texts().items():
    #         self.__save_rich_text(rich_text)
    #         rich_text_id = rich_text.calculate_id()
    #         self.store.get_relation_store().add_relation(rich_text_id, rich_text_id)
    #         # rich_text_enc["body"]["rich_texts"][key] = rich_text_id


    #     self.store.get_object_store().put_object(rich_text_id, rich_text.encode())

    # def __save_email(self, email: EmailObject):
    #     email_id = email.calculate_id()
    #     # email_enc = dict()
    #     # email_enc["desc"] = email.desc
    #     # email_enc["body"] = {"content": None}
    #     self.__save_rich_text(email.get_rich_text())
    #     rich_text_id = email.get_rich_text().calculate_id()
    #     self.store.get_relation_store().add_relation(rich_text_id, email_id)
    #     # email_enc["body"]["content"] = rich_text_id
    #     self.store.get_object_store().put_object(email_id, email.encode())

    
    # def __save_object(self, object: KnowledgeObject):
    #     if object.get_object_type() == ObjectType.Document:
    #         self.__save_document(object)
    #     if object.get_object_type() == ObjectType.Image:
    #         self.__save_image(object)
    #     if object.get_object_type() == ObjectType.Video:
    #         self.__save_video(object)
    #     if object.get_object_type() == ObjectType.RichText:
    #         self.__save_rich_text(object)
    #     if object.get_object_type() == ObjectType.Email:
    #         self.__save_email(object)
    #     else:
    #         pass

    async def insert_object(self, object: KnowledgeObject):
        self.store.get_object_store().put_object(object.calculate_id(), object.encode())
        await self.__do_embedding(object)

    async def query_prompt(self, prompt: AgentPrompt):
        logging.info(f"query_prompt: {prompt}")
        objects = await self.query_objects(prompt)
        knowledge_prompt = self.prompt_from_objects(objects)
        logging.info(f"prompt_from_objects result: {knowledge_prompt.as_str()}")
       
        return knowledge_prompt

    async def query_objects(self, prompt: AgentPrompt) -> [ObjectID]:
        results = []
        for msg in prompt.messages:
            if msg["role"] == "user":
                vector = await self.compute_kernel.do_text_embedding(msg["content"])
                object_ids = await self.store.get_vector_store("default").query(vector, 10)
                results.extend(object_ids)
        return results

    def __load_object(self, object_id: ObjectID) -> KnowledgeObject:
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
        

    def prompt_from_objects(self, object_ids: [ObjectID]) -> AgentPrompt:
        results = dict()
        for object_id in object_ids:
            parents = self.store.get_relation_store().get_related_root_objects(object_id)
            # last parent is the root object
            root_object_id = parents[0] if parents else object_id
            logging.info(f"object_id: {str(object_id)} root_object_id: {str(root_object_id)}")
            if str(root_object_id) in results:
                results[str(root_object_id)].append(object_id)
            else:
                results[str(root_object_id)] = [root_object_id, object_id]

        content = "*** I have provided the following known information for your reference with json format:\n"
        result_desc = []
        for result in results.values():
            # first element in result is the root object
            root_object_id = result[0]
            if root_object_id.get_object_type() == ObjectType.Email:
                email = self.__load_object(root_object_id)
                desc = email.get_desc()
                desc["type"] = "email"
                desc["contents"] = []
                result_desc.append(desc)
                upper_list = desc["contents"]
                result = result[1:]
            else:
                upper_list = result_desc
            
            for object_id in result:
                if object_id.get_object_type() == ObjectType.Chunk:
                    upper_list.append({"type": "text", "content": self.store.get_chunk_reader().get_chunk(object_id).read().decode("utf-8")})
                if object_id.get_object_type() == ObjectType.Image:
                    image = self.__load_object(object_id)
                    desc = image.get_desc()
                    desc["type"] = "image"
                    upper_list.append(desc)
                if object_id.get_object_type() == ObjectType.Video:
                    video = self.__load_object(object_id)
                    desc = video.get_desc()
                    desc["type"] = "video"
                    upper_list.append(desc)
                else:
                    pass
        content += json.dumps(result_desc)
        content += ".\n"

        prompt = AgentPrompt()
        prompt.messages.append({"role": "user", "content": content})    

        return prompt


    