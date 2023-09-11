from knowledge.object.object_id import ObjectType
from ..object import KnowledgeObject
from ..data import ChunkList, ChunkListWriter
from ..object import ObjectType
from .video_object import VideoObjectBuilder, VideoObject
from .image_object import ImageObjectBuilder, ImageObject
from .document_object import DocumentObjectBuilder, DocumentObject

class RichTextObject(KnowledgeObject):
    def __init__(self, images: dict = {}, videos: dict = {}, documents: dict = {}, rich_texts: dict = {}):
        desc = dict()
        desc["images"] = images
        desc["videos"] = videos
        desc["documents"] = documents
        desc["rich_texts"] = rich_texts
        
        super().__init__(ObjectType.RichText, desc)
        
     
    def add_image_with_key(self, key, image_object: ImageObject):
        assert self.desc["images"][key] == None
        self.desc["images"][key] = image_object
           
    def add_image(self, image_object: ImageObject):
        self.desc["images"][image_object.object_id()] = image_object
     
    def get_image_with_key(self, key) -> ImageObject:
        return self.desc["images"][key]

    def get_images(self) -> dict:
        return self.desc["images"]
       
    def add_video_with_key(self, key, video_object: VideoObject):
        assert self.desc["videos"][key] == None
        self.desc["videos"][key] = video_object
        
    def add_video(self, video_object: VideoObject):
        self.desc["videos"][video_object.object_id()] = video_object
        
    def get_video_with_key(self, key) -> VideoObject:
        return self.desc["videos"][key]
    
    def get_videos(self) -> dict:    
        return self.desc["videos"]
        
        
    def add_document_with_key(self, key, document_object: DocumentObject):
        assert self.desc["documents"][key] == None
        self.desc["documents"][key] = document_object
        
    def add_document(self, document_object: DocumentObject):
        self.desc["documents"][document_object.object_id()] = document_object
      
    def get_document_with_key(self, key) -> DocumentObject:
        return self.desc["documents"][key]
    
    def get_documents(self) -> dict:
        return self.desc["documents"]
      
    def add_rich_text_with_key(self, key, rich_text_object):
        assert self.desc["rich_texts"][key] == None
        self.desc["rich_texts"][key] = rich_text_object
        
    def add_rich_text(self, rich_text_object):
        self.desc["rich_texts"][rich_text_object.object_id()] = rich_text_object
        
    def get_rich_text_with_key(self, key):
        return self.desc["rich_texts"][key]
    
    def get_rich_texts(self) -> dict:
        return self.desc["rich_texts"]
    
    
class RichTextObjectBuilder:
    def __init__(self, folder: str):
        self.folder = folder
        
    def build(self) -> RichTextObject:
        # TODO
        return RichTextObject()