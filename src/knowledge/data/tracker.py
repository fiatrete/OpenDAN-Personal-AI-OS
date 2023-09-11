import sqlite3
import time
import logging
import os
from .chunk import ChunkID, PositionType, PositionFileRange
from typing import List

class ChunkTracker:
    def __init__(self, root_dir: str):
        if not os.path.exists(root_dir):
            os.makedirs(root_dir)
        file = os.path.join(root_dir, "chunk_tracker.db")
        logging.info(f"will init chunk tracker, db={file}")

        self.conn = sqlite3.connect(file)
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT NOT NULL,
                pos TEXT NOT NULL,
                pos_type TINYINT NOT NULL,
                insert_time UNSIGNED BIG INT NOT NULL,
                update_time UNSIGNED BIG INT NOT NULL,
                flags INTEGER DEFAULT 0,
                PRIMARY KEY(id, pos, pos_type)
            )
        """
        )
        self.conn.commit()

    def add_position(
        self, chunk_id: ChunkID, position: str, position_type: PositionType
    ):
        logging.debug(f"add chunk position: {chunk_id}, {position}, {position_type}")

        insert_time = update_time = int(time.time())
        self.cursor.execute(
            """
            INSERT OR REPLACE INTO chunks (id, pos, pos_type, insert_time, update_time)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                str(chunk_id),
                position,
                position_type.value,
                insert_time,
                update_time,
            ),
        )
        self.conn.commit()

    def remove_position(self, chunk_id: ChunkID):
        logging.info(f"remove chunk position: {chunk_id}")

        self.cursor.execute(
            """
            DELETE FROM chunks WHERE id = ?
        """,
            (str(chunk_id),),
        )
        self.conn.commit()

    def get_position(self, chunk_id: ChunkID) -> List[(str, PositionType)]:
        self.cursor.execute(
            """
            SELECT pos, pos_type FROM chunks WHERE id = ?
        """,
            (str(chunk_id),),
        )
        return self.cursor.fetchmany()
