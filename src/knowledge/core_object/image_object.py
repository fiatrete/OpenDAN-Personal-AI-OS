from ..object import KnowledgeObject
from ..data import ChunkList, ChunkListWriter
from ..object import ObjectType
from .. import KnowledgeStore

# desc
#   meta
#   tags
#   hash: "file-hash",
#   exif: {}
# body
#   chunk_list: [chunk_id, chunk_id, ...]


class ImageObject(KnowledgeObject):
    def __init__(self, meta: dict, tags: dict, exif: dict, chunk_list: ChunkList):
        desc = dict()
        body = dict()
        desc["meta"] = meta
        desc["exif"] = exif
        desc
        desc["hash"] = chunk_list.hash.to_base58()
        body["chunk_list"] = chunk_list.chunk_list

        super().__init__(ObjectType.Image, desc, body)

    def get_meta(self):
        return self.desc["meta"]

    def get_exif(self):
        return self.desc["exif"]

    def get_tags(self):
        return self.desc["tags"]
    
    def get_hash(self):
        return self.desc["hash"]

    def get_chunk_list(self):
        return self.body["chunk_list"]


from PIL import Image
from PIL.ExifTags import TAGS


def get_exif_data(image_path: str):
    with Image.open(image_path) as image:
        exif_data = image._getexif()

    if exif_data is not None:
        return {
            TAGS.get(key): exif_data[key]
            for key in exif_data.keys()
            if key in TAGS and isinstance(exif_data[key], (bytes, str))
        }
    else:
        return {}


class ImageObjectBuilder:
    def __init__(self, meta: dict, tags: dict, image_file: str):
        self.meta = meta
        self.tags = tags
        self.image_file = image_file
        self.restore_file = False

    def set_meta(self, meta: dict):
        self.meta = meta
        return self
    
    def set_tags(self, tags: dict):
        self.tags = tags
        return self

    def set_image_file(self, image_file: str):
        self.image_file = image_file
        return self

    def set_restore_file(self, restore_file: bool):
        self.restore_file = restore_file
        return self

    def build(self) -> ImageObject:
        chunk_list = KnowledgeStore().get_chunk_list_writer().create_chunk_list_from_file(
            self.image_file, 1024 * 1024 * 4, self.restore_file
        )
        exif = get_exif_data(self.image_file)
        return ImageObject(self.meta, self.tags, exif, chunk_list)
