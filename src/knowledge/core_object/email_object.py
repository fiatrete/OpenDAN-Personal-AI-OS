from .rich_text_object import RichTextObject, RichTextObjectBuilder
from ..object import ObjectID, ObjectType, KnowledgeObject
from .document_object import DocumentObjectBuilder
from .image_object import ImageObjectBuilder
from .video_object import VideoObjectBuilder
from .rich_text_object import RichTextObjectBuilder
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
        return self.body["rich_text"]


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

                document = DocumentObjectBuilder({}, {}, text).build()
                documents = {"email.txt": document}
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
                    images[image_file] = image
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
                    videos[video_file] = video
                except Exception as e:
                    logging.error(f"Failed to read video file {video_path} {e}")
                    continue

        # Create RichTextObject
        rich_text = RichTextObject(images, videos, documents)

        # Create EmailObject
        return EmailObject(meta, {}, rich_text)
