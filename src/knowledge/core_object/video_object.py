from ..object import KnowledgeObject
from ..data import ChunkList, ChunkListWriter
from ..object import ObjectType


# desc
#   meta
#   tags
#   hash: "file-hash",
#   info: {}
# body
#   chunk_list: [chunk_id, chunk_id, ...]


class VideoObject(KnowledgeObject):
    def __init__(self, meta: dict, tags: dict, info: dict, chunk_list: ChunkList):
        desc = dict()
        body = dict()
        desc["meta"] = meta
        desc["tags"] = tags
        desc["info"] = info
        desc["hash"] = chunk_list.hash.to_base58()
        body["chunk_list"] = chunk_list.chunk_list

        super().__init__(ObjectType.Video, desc, body)

    def get_meta(self):
        return self.desc["meta"]

    def get_tags(self):
        return self.desc["tags"]

    def get_info(self):
        return self.desc["info"]

    def get_hash(self):
        return self.desc["hash"]

    def get_chunk_list(self):
        return self.body["chunk_list"]


from moviepy.editor import VideoFileClip


def get_video_info(video_path: str) -> dict:
    clip = VideoFileClip(video_path)
    return {
        "duration": clip.duration,  # Duration in seconds
        "fps": clip.fps,  # Frames per second
        "nframes": clip.reader.nframes,  # Total number of frames
        "size": clip.size,  # Size of the frames (width, height)
    }


class VideoObjectBuilder:
    def __init__(self, meta: dict, tags: dict, video_file: str):
        self.meta = meta
        self.tags = tags
        self.video_file = video_file
        self.restore_file = False

    def set_meta(self, meta: dict):
        self.meta = meta
        return self
    
    def set_tags(self, tags: dict):
        self.tags = tags
        return self

    def set_video_file(self, video_file: str):
        self.video_file = video_file
        return self

    def set_restore_file(self, restore_file: bool):
        self.restore_file = restore_file
        return self

    def build(self) -> VideoObject:
        chunk_list = ChunkListWriter.create_chunk_list_from_file(
            self.video_file, 1024 * 1024 * 4, self.restore_file
        )
        info = get_video_info(self.video_file)
        return VideoObject(self.meta, self.tags, info, chunk_list)
