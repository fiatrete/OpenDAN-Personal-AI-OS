from .rich_text_object import RichTextObject, RichTextObjectBuilder
from ..object import ObjectID, ObjectType, KnowledgeObject


class EmailObject(KnowledgeObject):
    def __init__(self, meta: dict, tags: dict, rich_text: RichTextObject):
        desc = dict()
        body = dict()
        desc["meta"] = meta
        desc["tags"] = tags

        # FIXME rich text content store in desc or body? which one is better?
        body["content"] = rich_text

        super().__init__(ObjectType.Email, desc, body)

    def get_meta(self):
        return self.desc["meta"]

    def get_tags(self):
        return self.desc["tags"]

    def get_rich_text(self):
        return self.body["rich_text"]


class EmailObjectBuilder:
    def __init__(self, meta: dict, tags: dict, folder: str):
        self.meta = meta
        self.tags = tags
        self.folder = folder

    def set_meta(self, meta: dict):
        self.meta = meta
        return self

    def set_tags(self, tags: dict):
        self.tags = tags
        return self

    def set_folder(self, folder: str):
        self.folder = folder
        return self

    def build(self) -> EmailObject:
        content = RichTextObjectBuilder(self.folder).build()
        return EmailObject(self.meta, self.tags, content)
