import os
import logging
import json
import imaplib
import mailparser
from knowledge import *
from aios_kernel.storage import AIStorage


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
        self.mail_local_root = os.path.join(self.env.pipeline_path, self.config.get("address"))
        os.makedirs(self.mail_local_root)

    async def next(self):
        while True:
            _, data = self.client.uid('search', None, "ALL")
            uid_list = data[0].split()
            if uid_list.len() == 0:
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
                    _, email_data = self.client.uid('fetch', uid, message_parts)
                    mail = mailparser.parse_from_bytes(email_data[0][1])
                    self.save_email(_uid, mail)

            yield (None, None)

    