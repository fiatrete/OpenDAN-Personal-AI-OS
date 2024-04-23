import os
import logging
import json
import string
from aios import *
from .mail import Mail, MailStorage


class LocalEmail:
    def __init__(self, env: KnowledgePipelineEnvironment, config:dict): 
        self.config = config
        self.env = env
        path = string.Template(config["path"]).substitute(myai_dir=AIStorage.get_instance().get_myai_dir())
        self.mail_storage = MailStorage(path, config.get("watch"))

    async def next(self):
        while True:
            parsed = None
            journals = self.env.journal.latest_journals(1)
            if len(journals) == 1:
                latest_journal = journals[0]
                if latest_journal.is_finish():
                    yield None
                    continue
                parsed = latest_journal.get_input()
            
            mail_id = self.mail_storage.next_mail_id(parsed)
            if mail_id is None:
                yield (None, None)
            else:
                yield (mail_id, str(mail_id))


class LocalEmailWithFilter:
    def __init__(self, env: KnowledgePipelineEnvironment, config:dict):
        pass