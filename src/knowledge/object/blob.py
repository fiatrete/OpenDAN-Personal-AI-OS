import os
import shutil
from .object import ObjectID


class FileBlobStorage:
    def __init__(self, root):
        self.root = root

    def get_full_path(self, object_id: ObjectID, auto_create: bool = True):
        if os.name == "nt":  # Windows
            hash_str = object_id.to_base36()
            len = 3
        else:
            hash_str = str(object_id)
            len = 2

        tmp, first = hash_str[:-len], hash_str[-len:]
        second = tmp[-len:]

        if os.name == "nt":  # Windows
            if second in ["con", "aux", "nul", "prn"]:
                second = tmp[-(len + 1) :]
            if first in ["con", "aux", "nul", "prn"]:
                first = f"{first}_"

        path = os.path.join(self.root, first, second)
        if auto_create and not os.path.exists(path):
            os.makedirs(path)

        path = os.path.join(path, hash_str)

        return path

    def write_sync(self, path: str, contents: bytes):
        with open(path, "wb") as f:
            f.write(contents)

    def put(self, object_id: ObjectID, contents: bytes):
        full_path = self.get_full_path(object_id)
        self.write_sync(full_path, contents)

    def get(self, object_id: ObjectID) -> bytes:
        full_path = self.get_full_path(object_id)
        with open(full_path, "rb") as f:
            return f.read()

    def delete(self, object_id: ObjectID):
        full_path = self.get_full_path(object_id)
        os.remove(full_path)

    def exists(self, object_id: ObjectID) -> bool:
        full_path = self.get_full_path(object_id)
        return os.path.exists(full_path)
