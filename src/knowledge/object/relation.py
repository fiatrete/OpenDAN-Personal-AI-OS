# define a relation store class
from .object_id import ObjectID


class ObjectRelationStore:
    def __init__(self, root_dir: str):
        pass

    def add_relation(self, object: ObjectID, parent: ObjectID):
        pass

    def get_related_objects(self, object: ObjectID) -> [ObjectID]:
        pass

    def delete_relation(self, object_id: ObjectID) -> [ObjectID]:
        pass