# define a relation store class
from .object_id import ObjectID
import sqlite3
from typing import List, Tuple, Optional
import logging
import os
from enum import Enum


class ObjectRelationType(Enum):
    Parent = 1


class ObjectRelationStore:
    def __init__(self, root_dir: str):
        if not os.path.exists(root_dir):
            os.makedirs(root_dir)
        file = os.path.join(root_dir, "relation.db")
        logging.info(f"will init object relation store, db={file}")

        self.conn = sqlite3.connect(file)
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS relations (
                object_id TEXT,
                assoc_id TEXT,
                relation_type TEXT,
                PRIMARY KEY (object_id, assoc_id, relation_type)
            )
        """
        )

    def add_relation(
        self,
        object_id: ObjectID,
        assoc_id: ObjectID,
        relation_type: ObjectRelationType = ObjectRelationType.Parent,
    ):
        if relation_type == None:
            relation_type = ObjectRelationType.Parent

        self.cursor.execute(
            """
            INSERT OR IGNORE INTO relations (object_id, assoc_id, relation_type)
            VALUES (?, ?, ?)
        """,
            (str(object_id), str(assoc_id), relation_type.value),
        )
        self.conn.commit()

    def get_related_objects(
        self, object_id: ObjectID, relation_type: Optional[ObjectRelationType] = None
    ) -> List[ObjectID]:
        if relation_type:
            self.cursor.execute(
                """
                SELECT assoc_id FROM relations WHERE object_id = ? AND relation_type = ?
            """,
                (str(object_id), relation_type.value),
            )
        else:
            self.cursor.execute(
                """
                SELECT assoc_id FROM relations WHERE object_id = ?
            """,
                (str(object_id),),
            )
        return [ObjectID.from_base58(row[0]) for row in self.cursor.fetchall()]

    def get_related_root_objects(
        self, object_id: ObjectID, relation_type: Optional[ObjectRelationType] = None
    ) -> List[ObjectID]:
        root_objects = []
        related_objects = self.get_related_objects(object_id, relation_type)
        history = []
        history.append(object_id)

        while related_objects:
            for obj in related_objects:
                next_related_objects = self.get_related_objects(obj, relation_type)
                if not next_related_objects:
                    if obj not in root_objects:
                        root_objects.append(obj)
                else:
                    for related_object in next_related_objects:
                        if obj not in history:
                            related_objects.append(related_object)
                        else:
                            logging.warning(
                                f"loop detected: {obj} <-> {related_object}"
                            )
            related_objects = next_related_objects

        return root_objects

    def delete_relation(self, object_id: ObjectID):
        self.cursor.execute(
            """
            DELETE FROM relations WHERE object_id = ?
        """,
            (str(object_id),),
        )
        self.conn.commit()
