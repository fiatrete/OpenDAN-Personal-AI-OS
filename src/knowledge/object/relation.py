# define a relation store class
import sqlite3
import os
import logging
from .object_id import ObjectID


class ObjectRelationStore:
    def __init__(self, root_dir: str):
        if not os.path.exists(root_dir):
            os.makedirs(root_dir)
        file = os.path.join(root_dir, "relationships.db")
        logging.info(f"will init chunk tracker, db={file}")

        self.conn = sqlite3.connect(file)
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS relationships (
                id TEXT NOT NULL,
                parent TEXT NOT NULL,
                PRIMARY KEY(id, parent)
            )
        """
        )
        self.conn.commit()

    def add_relation(self, object: ObjectID, parent: ObjectID):
        self.cursor.execute(
            """
            INSERT INTO relationships (id, parent)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                str(object),
                str(parent),
            ),
        )
        self.conn.commit()

    def get_related_objects(self, object: ObjectID) -> [ObjectID]:
        parents = []
        cur = object
        while True:
            self.cursor.execute(
                """
                SELECT id, parent FROM relationships WHERE id = ?
            """,
                (str(cur),),
            )
            parent = self.cursor.fetchone()
            if parent is None:
                break
            parents.append(parent)
            cur = parent

    def delete_relation(self, object_id: ObjectID) -> [ObjectID]:
        self.cursor.execute(
            """
            DELETE FROM relationships WHERE id = ?
        """,
            (str(object_id),),
        )
        self.conn.commit()