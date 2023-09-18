from .. import KnowledgeStore
from .rich_text_object import RichTextObject, RichTextObjectBuilder
from ..object import ObjectID, ObjectType, KnowledgeObject
from .document_object import DocumentObjectBuilder
from .image_object import ImageObjectBuilder
from .video_object import VideoObjectBuilder
import os
import json
import logging


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
        return self.body["content"]


"""
EmailObject folder structure:
.
├── email.txt
└── meta.json
    ├── image
    │   ├── image1.jpg
    │   ├── image2.jpg
    │   └── ...
    ├── video
    │   ├── video1.mp4
    │   ├── video2.mv
    │   └── ...
    └── audio
        ├── audio1.m4a
        ├── audio2.flac
        └── ...
EmailObjectBuilder will read the target folder and build the EmailObject
Store meta.json to meta in EmailObject
Store email.txt to DocumentObject and RichTextObject in EmailObject
Store very image file in image folder to ImageObject and RichTextObject in EmailObject, etc
"""


class EmailObjectBuilder:
    def __init__(self, tags: dict, folder: str):
        self.tags = tags
        self.folder = folder

    def set_tags(self, tags: dict):
        self.tags = tags
        return self

    def set_folder(self, folder: str):
        self.folder = folder
        return self

    def build(self) -> EmailObject:
        
        # Just get the object store and relation store from global KnowledgeStore
        store = KnowledgeStore().get_object_store()
        relation = KnowledgeStore().get_relation_store()
        
        # Read meta.json
        meta = {}
        meta_file = os.path.join(self.folder, "meta.json")
        if os.path.exists(meta_file):
            logging.info(f"Will read meta.json {meta_file}")
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        else:
            logging.info(f"Meta file missing! {meta_file}")

        # Read email.txt
        documents = {}
        content_file = os.path.join(self.folder, "email.txt")
        if os.path.exists(content_file):
            logging.info(f"Will read email.txt {content_file}")

            try:
                with open(content_file, "r", encoding="utf-8") as f:
                    text = f.read()

                document = DocumentObjectBuilder({}, {}, text).build(relation_store=relation)
                document_id = document.calculate_id()
                store.put_object(document_id, document.encode())
                documents = {"email.txt": document_id}
            except Exception as e:
                logging.error(f"Failed to read email.txt {content_file} {e}")
        else:
            logging.info(f"Content file missing! {content_file}")

        # Process image files
        images = {}
        image_dir = os.path.join(self.folder, "image")
        if os.path.exists(image_dir):
            for image_file in os.listdir(image_dir):
                image_path = os.path.join(image_dir, image_file)
                logging.info(f"Will read image file {image_path}")

                try:
                    image = ImageObjectBuilder({}, {}, image_path).build()
                    image_id = image.calculate_id()
                    store.put_object(image_id, image.encode())
                    images[image_file] = image_id
                except Exception as e:
                    logging.error(f"Failed to read image file {image_path} {e}")
                    continue

        # Process video files
        videos = {}
        video_dir = os.path.join(self.folder, "video")
        if os.path.exists(video_dir):
            for video_file in os.listdir(video_dir):
                video_path = os.path.join(video_dir, video_file)
                logging.info(f"Will read video file {video_path}")

                try:
                    video = VideoObjectBuilder({}, {}, video_path).build()
                    video_id = video.calculate_id()
                    store.put_object(video_id, video.encode())
                    videos[video_file] = video_id
                except Exception as e:
                    logging.error(f"Failed to read video file {video_path} {e}")
                    continue

        # Create RichTextObject
        rich_text = RichTextObject(images, videos, documents)
        rich_text_id = rich_text.calculate_id()
        
        # build relations with rich_text
        for image_id in images.values():
            relation.add_relation(image_id, rich_text_id)
        for video_id in videos.values():
            relation.add_relation(video_id, rich_text_id)
        for document_id in documents.values():
            relation.add_relation(document_id, rich_text_id)
            
        # Create EmailObject
        email_object = EmailObject(meta, {}, rich_text)
        email_object_id = email_object.calculate_id()
        store.put_object(email_object_id, email_object.encode())
        
        # build relations with email_object
        relation.add_relation(rich_text_id, email_object_id)
        
        return email_object
