import os
import logging
from .blob import FileBlobStorage
from .object_id import ObjectID


class ObjectStore:
    def __init__(self, root_dir: str):
        logging.info(f"will init object blob store, root_dir={root_dir}")

        blob_dir = os.path.join(root_dir, "blob")
        if not os.path.exists(blob_dir):
            logging.info(f"will create blob dir: {blob_dir}")
            os.makedirs(blob_dir)
        self.blob = FileBlobStorage(blob_dir)

    def put_object(self, object_id: ObjectID, contents: bytes):
        self.blob.put(object_id, contents)

    def get_object(self, object_id: ObjectID) -> bytes:
        return self.blob.get(object_id)

    def delete_object(self, object_id: ObjectID):
        self.blob.delete(object_id)
