import unittest
import sys
import os
import sqlite3
directory = os.path.dirname(__file__)
sys.path.append(directory + '/../src')

from aios_kernel import ChatSessionDB


class TestChatDatabase(unittest.TestCase):

    def setUp(self):
        """Function to setup the test case"""
        self.db_file = 'test_chat.db'
        self.chat_db = ChatSessionDB(self.db_file)

    def tearDown(self):
        """Function to cleanup after the test case"""
        self.chat_db.close()
        os.remove(self.db_file)

    def test_database_creation(self):
        """Test if the database is created"""
        self.assertTrue(os.path.exists(self.db_file))

    def test_table_creation(self):
        """Test if the tables are created in the database"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Check if ChatSessions table exists
        cursor.execute("""
            SELECT count(name) FROM sqlite_master WHERE type='table' AND name='ChatSessions'
        """)
        self.assertEqual(cursor.fetchone()[0], 1)

        # Check if Messages table exists
        cursor.execute("""
            SELECT count(name) FROM sqlite_master WHERE type='table' AND name='Messages'
        """)
        self.assertEqual(cursor.fetchone()[0], 1)

        conn.close()

    def test_insert_and_get_session(self):
        """Test if we can insert and retrieve a session"""
        session_id = "session1"
        session_owner = "user1"
        session_topic = "topic1"
        start_time = "2023-08-28 12:00:00"

        self.chat_db.insert_chatsession(session_id,session_owner, session_topic, start_time)
        session = self.chat_db.get_chatsession_by_id(session_id)

        self.assertEqual(session, (session_id,session_owner,session_topic, start_time))

    def test_insert_and_get_message(self):
        """Test if we can insert and retrieve a message"""
        message_id = "message1"
        session_id = "session1"
        sender_id = "user1"
        receiver_id = "user2"
        timestamp = "2023-08-28 12:30:00"
        content = "Hello, world!"
        status = 0

        self.chat_db.insert_message(message_id, session_id, sender_id, receiver_id, timestamp, content, status)
        message = self.chat_db.get_message_by_id(message_id)

        self.assertEqual(message, (message_id, session_id, sender_id, receiver_id, timestamp, content, status))


if __name__ == '__main__':
    unittest.main()