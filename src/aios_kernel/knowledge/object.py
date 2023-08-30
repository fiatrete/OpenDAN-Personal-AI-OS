
# define a object type enum
from abc import ABC


class ObjectType(Enum):
    TextChunk = 1
    Image = 2
    Email = 101


# define a object ID class to identify a object
class ObjectID: # pylint: disable=too-few-public-methods
    def __init__(self, object_type, digist):
        self.object_type = object_type
        self.digist = digist

    def __str__(self):
        return f"{self.object_type.name}:{self.digist}"
    

# define a object class
class KnowledgeObject(ABC): # pylint: disable=too-few-public-methods
    def __init__(self, object_type):
        self.object_type = object_type

    @abstractmethod
    def get_id(self) -> ObjectID:
        pass

    # define a to binary method to convert object to binary
    @abstractmethod
    def to_binary(self) -> bytes:
        pass

    # define a from binary method to convert binary to object
    @abstractmethod
    def from_binary(self, binary: bytes):
        pass


# define a text chunk class
class TextChunkObject(KnowledgeObject): # pylint: disable=too-few-public-methods
    def __init__(self, text):
        super().__init__(ObjectType.TextChunk)
        self.text = text


# define a image class
class ImageObject(KnowledgeObject): # pylint: disable=too-few-public-methods
    def __init__(self, meta, path):
        super().__init__(ObjectType.Image)
        self.meta = meta
        self.path = path


# define a email class
class EmailObject(KnowledgeObject): # pylint: disable=too-few-public-methods
    def __init__(self, meta):
        super().__init__(ObjectType.Email)
        self.meta = meta
        self.text = []
        self.images = []

    
