import asyncio
import json
import mailparser
import base64
import requests
import datetime
from bs4 import BeautifulSoup
import sqlite3
import html2text
from knowledge import *

class Mail:
    def __init__(self, **kwargs) -> None:
        self.from_addr = kwargs.get("From")
        self.to_addr = kwargs.get("To")
        self.subject = kwargs.get("Subject")
        self.date = kwargs.get("Date")
        self.bcc = kwargs.get("BCC")
        self.cc = kwargs.get("CC")
        self.reply_to = None
        self.id: str = None
        self.content: str = None

    def to_prompt(self) -> str:
        prompt = {
            "id": self.id,
            "subject": self.subject,
            "from": self.from_addr,
            "date": self.date, 
            "content": self.content 
        }
        return json.dumps(prompt)
    
    @classmethod
    def prompt_desc(cls) -> dict:
        return '''a mail contains following fileds: {
            id: a guid string to identify a mail
            subject: subject of this mail
            from: sender address of this mail
            date: date of this mail
            content: content of this mail
        }
        '''

    def get_date(self) -> datetime.datetime:
        datetime.datetime.strptime(self.date, "%Y-%m-%d %H:%M")

    def calculate_id(self) -> str:
        desc = {
            "from_addr": self.from_addr,
            "to_addr": self.to_addr,
            "subject": self.subject, 
            "date": self.date,
            "content": self.content, 
            "reply_to": self.reply_to
        }
        id = str(KnowledgeObject(ObjectType.Email, desc).calculate_id())
        self.id = id
        return id

class MailStorage:
    def __init__(self, root, watch=False):
        self.root = root
        if not os.path.exists(root):
            os.makedirs(root)
        db_file = os.path.join(root, "mail.db")

        self.conn = sqlite3.connect(db_file)
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS mails (
                uid INTEGER PRIMARY KEY,
                object_id TEXT,
                date DATETIME,
                from_addr TEXT
            )
        """
        )

        if watch:
            asyncio.create_task(self.watch_root())

    def object_id_to_uid(self, object_id):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT uid FROM mails WHERE object_id = ?
        """,
            (object_id,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        return None

    def uid_to_object_id(self, uid):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT object_id FROM mails WHERE uid = ?
        """,
            (uid,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    
    def lastest_uid(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT uid FROM mails ORDER BY uid DESC LIMIT 1
        """
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    
    def lastest_mail_id(self):
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT object_id FROM mails ORDER BY uid DESC LIMIT 1
        """
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
    
    def next_mail_id(self, id):
        uid = 0 if id is None else self.object_id_to_uid(id)
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT object_id FROM mails WHERE uid > ? ORDER BY uid ASC LIMIT 1
        """,
            (uid,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        return None
        
    

    def get_mail_by_id(self, id):
        uid = self.object_id_to_uid(id)
        mail = Mail()
        mail.id = id
        mail_dir = self.mail_dir(uid)
        mail_json = json.load(open(f"{mail_dir}/mail.json", "r", encoding='utf-8'))
        mail.__dict__.update(mail_json)
        with open(f"{mail_dir}/mail.txt", "r", encoding='utf-8') as f:
            mail_content = f.read()
        mail.content = mail_content
        return mail

    def mail_dir(self, uid):
        return os.path.join(self.root, str(uid))
    
    # for debug
    async def watch_root(self):
        while True:
            latest_uid = self.lastest_uid()
            for uid in os.listdir(self.root):
                mail_dir = os.path.join(self.root, uid)
                if uid.isdigit() and os.path.isdir(mail_dir):
                    uid = int(uid)
                    if uid <= latest_uid:
                        continue
                    mail = Mail()
                    mail_json = json.load(open(f"{mail_dir}/mail.json", "r", encoding='utf-8'))
                    
                    mail.__dict__.update(mail_json)
                    # mail content
                    with open(f"{mail_dir}/mail.txt", "r", encoding='utf-8') as f:
                        mail_content = f.read()
                    mail.content = mail_content
                    mail.calculate_id()
                    cursor = self.conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO mails (uid, object_id, date, from_addr)
                        VALUES (?, ?, ?, ?)
                    """,
                        (uid, mail.id, mail.get_date(), mail.from_addr),
                    )
                    self.conn.commit()
            await asyncio.sleep(10)
    
    def download(self, uid, mail: mailparser.MailParser):
        mail_dir = self.mail_dir(uid)
        os.makedirs(dir)

        meta = json.loads(mail.mail_json)
        mail = Mail(**meta)
        reply_to = meta.get("In-Reply-To")
        if reply_to:
            mail.reply_to = self.uid_to_object_id(reply_to)
        
        h = html2text.HTML2Text()
        h.ignore_links = True
        h.ignore_images = True
        mail_content = h.handle(mail.body)    
        mail.content = mail_content
       
        mail.calculate_id()
        del mail.content
        json.dump(mail.__dict__, open(f"{mail_dir}/mail.json", "w", encoding='utf-8'))
        
        # save mail content
        with open(f"{mail_dir}/mail.txt", "w", encoding='utf-8') as f:
            f.write(mail_content)
        
        for attachment in mail.attachments:
            if attachment['mail_content_type'] in ['image/png', 'image/jpeg', 'image/gif']:
                filename = attachment['filename']
                filefullname = f"{mail_dir}/{filename}"
                image_data = attachment['payload']
                try:
                    image_data = base64.b64decode(image_data)
                except base64.binascii.Error:
                    image_data = image_data.encode()
                with open(filefullname, 'wb') as f:
                    f.write(image_data)
                    logging.info(f"save email image {filename} success")

        # get all image urls
        soup = BeautifulSoup(mail.body, 'html.parser')
        img_tags = soup.find_all('img')
        img_urls = [img['src'] for img in img_tags if 'src' in img.attrs]
        logging.info(f'Found {len(img_urls)} images in email body')

        name_count = 0
        
        for img_url in img_urls:
            # keep the original image filename(last of url)
            ext = img_url.split('/')[-1].split('.')[-1]
            img_filename = os.path.join(mail_dir, f"{name_count}.{ext}")
            name_count += 1
            # download image 
            response = requests.get(img_url, stream=True)
            if response.status_code == 200:
                with open(img_filename, 'wb') as img_file:
                    for chunk in response.iter_content(1024):
                        img_file.write(chunk)
                logging.info(f'Downloaded {img_url} to {img_filename}')
            else:
                logging.info(f'Failed to download {img_url}')

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO mails (uid, object_id, date, from_addr)
            VALUES (?, ?, ?, ?)
        """,
            (uid, mail.id, mail.date, mail.from_addr),
        )

    