# define a knowledge base class
from . import AgentPrompt, ComputeKernel
from ..knowledge.object import KnowledgeObject, ObjectType, EmailObject, TextChunkObject, ImageObject
from ..knowledge.store import ObjectStorage
from ..knowledge.vector.vector_base import VectorBase

class KnowledgeBase:
    def __init__(self) -> None:
        self.object_store = ObjectStorage()
        self.vector_base = VectorBase()
        self.compute_kernel = ComputeKernel()

    async def insert(self, object: KnowledgeObject):
        if object.object_type == ObjectType.Email:
            email: EmailObject = object
            for text_id in email.text:
                [text, _] = self.object_store.get(text_id)
                text: TextChunkObject = text
                vector = await self.compute_kernel.do_text_embedding(text.text)
                self.vector_base.insert(vector, text_id)
            
            for image_id in email.images:
                [image, _] = self.object_store.get(image_id)
                image: ImageObject = image
                vector = await self.compute_kernel.do_text_embedding(image.meta)
                self.vector_base.insert(vector, image_id)
            
            vector = await self.compute_kernel.do_text_embedding(email.meta)
            self.vector_base.insert(vector, email.get_id())
        else:
            pass

    async def query(self, prompt: AgentPrompt) -> AgentPrompt:
        for msg in prompt.messages:
            if msg.role == "user":
                vector = await self.compute_kernel.do_text_embedding(msg.content)
                object_ids = self.vector_base.query(vector, 10)
                for object_id in object_ids:
                    if object_id.object_type == ObjectType.Email:
                        [object, email] = self.object_store.get(object_id)
                        if object.object_type == ObjectType.Email:
                            email: EmailObject = object
                            prompt.append(AgentPrompt())
                            prompt
                    
                

    