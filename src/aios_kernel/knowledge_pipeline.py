"""
Capture your email locally, and parse out the pictures in the email body and the pictures, videos and other files in the attachment. Subsequently, it supports vectorized analysis of your personal data and serves as a knowledge base to enable large language model answers. Better results.

An example of a local file is as follows:
├── data
│ └── alex0072@gmail.com
│   └── 5de3e52f3a6b90cabe6cbdd4ae3a5c5b
│     ├── email.txt
│     ├── meta.json
│     ├── image
│     │   ├── 0648B869@99C03070.DB94B354.jpg
│     └── body_image
│         ├── 11044884873.jpg
│         ├── 282985198265470.gif
│         └── dd-login-service-min.png

"""
import asyncio
import datetime
import sqlite3
import imaplib
import logging
import mailparser
import hashlib
import json
import base64
import chardet
import aiofiles

from bs4 import BeautifulSoup
import requests
import os
import toml
from .storage import AIStorage, UserConfigItem
from .knowledge_base import KnowledgeBase, ImageObjectBuilder, ObjectID, ObjectType, DocumentObjectBuilder

class KnowledgeJournal:
    def __init__(self, source_type: str, source_id: str, item_id: str, object_id: str, timestamp=None):
        # define a timestamp variable
        self.timestamp = datetime.datetime.now() if timestamp is None else timestamp
        self.object_id = object_id
        self.source_type = source_type
        self.source_id = source_id
        self.item_id = item_id

    def __str__(self) -> str:
        if self.source_type == "dir":
            object_id = ObjectID.from_base58(self.object_id)
            object_type = None
            if object_id.get_object_type() == ObjectType.Image:
                object_type = "image"
            else:
                pass
            return f"Add {object_type} from {os.path.join(self.source_id, self.item_id)}"
        if self.source_type == "email":
            pass


# init sqlite3 client
class KnowledgeJournalClient:
    def __init__(self):
        knowledge_dir = os.path.join(AIStorage.get_instance().get_myai_dir(), "knowledge")
        if not os.path.exists(knowledge_dir):
            os.makedirs(knowledge_dir)
        self.journal_path = os.path.join(knowledge_dir, "journal.db")
    
        conn = sqlite3.connect(self.journal_path)
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS journal (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                time DATETIME DEFAULT CURRENT_TIMESTAMP, 
                source_type TEXT,
                source_id TEXT,
                item_id TEXT, 
                object_id TEXT)'''
        )
        conn.commit()

    def insert(self, journal: KnowledgeJournal):
        conn = sqlite3.connect(self.journal_path)
        conn.execute(
            "INSERT INTO journal (time, source_type, source_id, item_id, object_id) VALUES (?, ?, ?, ?, ?)",
            (journal.timestamp, journal.source_type, journal.source_id, journal.item_id, journal.object_id),
        )
        conn.commit()

    def latest_journal(self, source_id: str) -> KnowledgeJournal:
        conn = sqlite3.connect(self.journal_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM journal WHERE source_id = ? ORDER BY id DESC LIMIT 1", (source_id,))
        result = cursor.fetchone()
        if result is None:
            return None
        else:
            (_, timestamp, source_type, sorce_id, item_id, object_id) = result
            return KnowledgeJournal(source_type, sorce_id, item_id, object_id, timestamp)
        
    def latest_journals(self, topn) -> [KnowledgeJournal]:
        conn = sqlite3.connect(self.journal_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM journal ORDER BY id DESC LIMIT ?", (topn,))
        return [KnowledgeJournal(source_type, sorce_id, item_id, object_id, timestamp) for (_, timestamp, source_type, sorce_id, item_id, object_id) in cursor.fetchall()]


class KnowledgeEmailSource:
    def __init__(self, config:dict): 
        self.config = config
        self.config["type"] = "email"
    
    def id(self):
        "::".join([self.config["imap_server"], self.config["address"]])

    @classmethod
    def user_config_items(cls):
        return [("address", "email address"),
                ("password", "email password"),
                ("imap_server", "imap server"),
                ("imap_port", "imap port")
                ]
    
    @classmethod
    def local_root(cls):
        user_data_dir = AIStorage.get_instance().get_myai_dir()
        return os.path.abspath(f"{user_data_dir}/email")    

    async def run_once(self):
        # read config from toml file
        # and read from config config.local.toml if exists (config.local.toml is ignored by git)
        self.client = self.email_client()
        await self.read_emails()

    def email_client(self) -> imaplib.IMAP4_SSL:
        logging.info(f"read email config from {self.config.get('imap_server')}")
        client = imaplib.IMAP4_SSL(
            host=self.config.get('imap_server'), 
            port=self.config.get('imap_port')
        )
        client.login(self.config.get('address'), self.config.get('password'))
        return client

    async def read_emails(self, folder: str = 'INBOX', imap_keyword: str = "UNSEEN"):
        self.client.select(folder)
        _, data = self.client.uid('search', None, imap_keyword)
        
        # get email uid list
        email_list = data[0].split()
        logging.info(f"got {len(email_list)} emails")
        email_list.reverse()
        for uid in email_list:
            if self.check_email_saved(uid):
                logging.info(f"email uid {uid} already saved")
            else:
                self.read_and_save_email(uid)
                logging.info(f"email uid {uid} saved")

    def read_and_save_email(self, uid: str):
        message_parts = "(BODY.PEEK[])"
        _, email_data = self.client.uid('fetch', uid, message_parts)
        mail = mailparser.parse_from_bytes(email_data[0][1])
        logging.info(f"got email subject [{mail.subject}]")
        self.save_email(mail)

    def get_local_dir_name(self, mail: mailparser.MailParser) -> str:
        dir =  f"{self.local_root()}/{self.config.get('address')}"
        name = f"{mail.subject}__{mail.date}"
        name = hashlib.md5(name.encode('utf-8')).hexdigest()
        return f"{dir}/{name}"

    def check_email_saved(self, uid: str):
        message_parts = "(BODY[HEADER])"
        _, email_data = self.client.uid('fetch', uid, message_parts)
        mail = mailparser.parse_from_bytes(email_data[0][1])
        logging.info(f"[{uid}]check email subject [{mail.subject}]")
        dir = self.get_local_dir_name(mail)
        logging.info(f"check email saved {dir}")
        file = f"{dir}/email.txt"
        if os.path.exists(file):
            return False
        return False

    # save email attachment(images)
    def save_email_attachment(self, mail: mailparser.MailParser, email_dir: str):
        for attachment in mail.attachments:
            if attachment['mail_content_type'] in ['image/png', 'image/jpeg', 'image/gif']:
                print('current mail have image attachment')
                img_dir = f"{email_dir}/image"
                if not os.path.exists(img_dir):
                    os.makedirs(img_dir)
                filename = attachment['filename']
                filefullname = f"{img_dir}/{filename}"
                image_data = attachment['payload']
                try:
                    image_data = base64.b64decode(image_data)
                except base64.binascii.Error:
                    image_data = image_data.encode()
                with open(filefullname, 'wb') as f:
                    f.write(image_data)
                    logging.info(f"save email image {filename} success")

    # save email body images(html content)
    def save_body_images(self, html_content: str, email_dir: str):
        # get all image urls
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tags = soup.find_all('img')
        img_urls = [img['src'] for img in img_tags if 'src' in img.attrs]
        logging.info(f'Found {len(img_urls)} images in email body')

        if not os.path.exists(email_dir):
            os.makedirs(email_dir)

        for img_url in img_urls:
            # keep the original image filename(last of url)
            img_filename = os.path.join(email_dir, img_url.split('/')[-1])
            # download image 
            response = requests.get(img_url, stream=True)
            if response.status_code == 200:
                with open(img_filename, 'wb') as img_file:
                    for chunk in response.iter_content(1024):
                        img_file.write(chunk)
                logging.info(f'Downloaded {img_url} to {img_filename}')
            else:
                logging.info(f'Failed to download {img_url}')

    # save email content to local dir
    def save_email(self, mail: mailparser.MailParser):
        dir = f"{self.local_root()}/{self.config.get('address')}"
        if not os.path.exists(dir):
            os.makedirs(dir)
        email_dir = self.get_local_dir_name(mail)
        logging.info(f"save email to {email_dir}")
        if not os.path.exists(email_dir):
            os.makedirs(email_dir)
        with open(f"{email_dir}/email.txt", "w") as f:
            f.write(mail.body)
        with open(f"{email_dir}/meta.json", "w", encoding='utf-8') as f:
            mail_dict = json.loads(mail.mail_json)
            if 'body' in mail_dict:
                del mail_dict['body']
            json.dump(mail_dict, f, ensure_ascii=False, indent=4)
            logging.info(f"save email meta info {f.name}")
        
        self.save_email_attachment(mail, email_dir)
        self.save_body_images(mail.body, f"{email_dir}/body_image")


class KnowledgeDirSource:
    def __init__(self, config):
        self.config = config
        self.config["type"] = "dir"

    @classmethod
    def user_config_items(cls):
        return [("path", "local dir path")]
    
    def id(self):
        return self.config["path"]

    def path(self):
        return self.config["path"]
    
    @staticmethod
    async def read_txt_file(file_path:str)->str:
        cur_encode = "utf-8"
        async with aiofiles.open(file_path,'rb') as f:
            cur_encode = chardet.detect(await f.read())['encoding']
        
        async with aiofiles.open(file_path,'r',encoding=cur_encode) as f:
            return await f.read()
        
    async def run_once(self):
        logging.debug(f"knowledge dir source {self.id()} run once")
        journal_client = KnowledgeJournalClient()
        latest_journal = journal_client.latest_journal(self.id())
        if latest_journal is not None:
            if os.path.getmtime(self.path()) <= latest_journal.timestamp:
                logging.debug(f"knowledge dir source {self.id()} ingnored for no update")
                return
        file_pathes = sorted(os.listdir(self.path()), key=lambda x: os.path.getctime(os.path.join(self.path(), x)))
        for rel_path in file_pathes:
            file_path = os.path.join(self.path(), rel_path)
            timestamp = os.path.getctime(file_path)
            if latest_journal is not None:
                if timestamp <= latest_journal.timestamp:
                    continue
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                logging.info(f"knowledge dir source {self.id()} found image file {file_path}")
                image = ImageObjectBuilder({}, {}, file_path).build()
                await KnowledgeBase().insert_object(image)
                journal_client.insert(KnowledgeJournal("dir", self.id(), rel_path, str(image.calculate_id()), timestamp))
            if ext in ['.txt']:
                logging.info(f"knowledge dir source {self.id()} found text file {file_path}")
                text = await self.read_txt_file(file_path)
    
                document = DocumentObjectBuilder({}, {}, text).build()
                await KnowledgeBase().insert_object(document)
                journal_client.insert(KnowledgeJournal("dir", self.id(), rel_path, str(document.calculate_id()), timestamp))
            



# define singleton class knowledge pipline
class KnowledgePipline:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = KnowledgePipline()
            cls._instance.__singleton_init__()

        return cls._instance
    
    def initial(self):
        config_path = self.__config_path()
        logging.info(f"initial knowledge pipline from {config_path}")
        if os.path.exists(config_path):
            config = toml.load(self.__config_path())
            for source_config in config["sources"]:
                if source_config['type'] == 'email':
                    self.add_email_source(KnowledgeEmailSource(source_config))
                if source_config['type'] == 'dir':
                    self.add_dir_source(KnowledgeDirSource(source_config))

    def __singleton_init__(self):
        self.knowledge_base = KnowledgeBase()
        self.email_sources = dict()
        self.dir_sources = dict()
        self.source_queue = list()
        self.run_lock = asyncio.Lock()
        asyncio.create_task(self.run_loop())
        

    def save_config(self):
        config = dict()
        config["sources"] = [source.config for source in self.source_queue]
        with open(self.__config_path(), "w") as f:
            toml.dump(config, f)
        

    @classmethod
    def __config_path(cls) -> str:
        user_data_dir = AIStorage.get_instance().get_myai_dir()
        return os.path.abspath(f"{user_data_dir}/etc/knowledge.cfg.toml")


    def add_email_source(self, source: KnowledgeEmailSource):
        if self.email_sources.get(source.id()) is not None: 
            return "already exists"
        self.email_sources[source.id()] = source
        self.source_queue.append(source)
        return None

    def add_dir_source(self, source: KnowledgeDirSource):
        if self.dir_sources.get(source.id()) is not None:
            logging.info(f"knowledge add source {source.id()} failed for already exists") 
            return "already exists"
        logging.info(f"knowledge added source {source.id()}") 
        self.dir_sources[source.id()] = source
        self.source_queue.append(source)
        return None
    
    def get_latest_journals(self, topn) -> [KnowledgeJournal]:
        return KnowledgeJournalClient().latest_journals(topn)
    
    async def run_loop(self):
        while True:
            await self.run_once()
            await asyncio.sleep(5)

    async def run_once(self):
        logging.info(f"knowledge pipeline started") 
        # sources = list()
        # async with self.run_lock:
        #     for source in self.source_queue:
        #         sources.append(source)
        # for source in sources: 
        #     await source.run_once()
        for source in self.source_queue:
            await source.run_once()
