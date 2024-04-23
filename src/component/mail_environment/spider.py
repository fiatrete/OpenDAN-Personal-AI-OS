import os
import logging
import json
import string
import imaplib
import mailparser

from knowledge import *
from aios_kernel.storage import AIStorage
from .mail import Mail, MailStorage


class EmailSpider:
    def __init__(self, env: KnowledgePipelineEnvironment, config:dict): 
        self.config = config
        self.env = env
        self.env.get_logger().info(f"read email config from {self.config.get('imap_server')}")
        self.client = imaplib.IMAP4_SSL(
            host=self.config.get('imap_server'), 
            port=self.config.get('imap_port')
        )
        self.client.login(self.config.get('address'), self.config.get('password'))
        self.client.select("INBOX")
        local_path = string.Template(config["path"]).substitute(myai_dir=AIStorage.get_instance().get_myai_dir())
        local_path = os.path.join(local_path, self.config.get('address'))
        self.mail_storage = MailStorage(local_path)
       

    async def next(self):
        while True:
            try:
                _, data = self.client.uid('search', None, "ALL")
            except Exception as e:
                self.env.get_logger().error(f"email spider error: {e}")
                yield (None, None)
                continue
            uid_list = data[0].split()
            if len(uid_list) == 0:
                yield (None, None)
                continue
            
            journals = self.env.journal.latest_journals(1)
            from_uid = 0
            if len(journals) == 1:
                latest_journal = journals[0]
                if latest_journal.is_finish():
                    yield None
                    continue
                from_uid = int(latest_journal.get_input())
                if int.from_bytes(uid_list[-1]) <= from_uid:
                    yield (None, None)
                    continue
            
            for uid in uid_list:
                _uid = int.from_bytes(uid)
                if _uid > from_uid:
                    message_parts = "(BODY.PEEK[])"
                    try:
                        _, email_data = self.client.uid('fetch', uid, message_parts)
                        mail = mailparser.parse_from_bytes(email_data[0][1])
                        id = self.mail_storage.download(_uid, mail)
                    except Exception as e:
                        self.env.get_logger().error(f"email spider error: {e}")
                        yield (None, None)
                        break
                    yield (ObjectID.from_base58(id), str(_uid))
                   

            yield (None, None)

    