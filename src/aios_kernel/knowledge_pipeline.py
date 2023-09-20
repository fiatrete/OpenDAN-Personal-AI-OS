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

import imaplib
import os
import toml
import logging
import mailparser
import hashlib
import json
import base64
from bs4 import BeautifulSoup
import requests

class EmailSpider:
    def __init__(self):
        # logger config
        self.logger = logging.getLogger('email spider')
        self.logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(name)s] [%(levelname)s] %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # read config from toml file
        # and read from config config.local.toml if exists (config.local.toml is ignored by git)
        self.config = toml.load('./rootfs/email/config.toml')
        if os.path.exists('./rootfs/email/config.local.toml'):
            self.config = toml.load('./rootfs/email/config.local.toml')

        self.client = self.email_client()

    def email_client(self) -> imaplib.IMAP4_SSL:
        self.logger.info(f"read email config from {self.config.get('EMAIL_IMAP_SERVER')}")
        client = imaplib.IMAP4_SSL(
            host=self.config.get('EMAIL_IMAP_SERVER'), 
            port=self.config.get('EMAIL_IMAP_PORT')
        )
        client.login(self.config.get('EMAIL_ADDRESS'), self.config.get('EMAIL_PASSWORD'))
        return client

    def list_box(self):
        _, mailbox_list = self.client.list()
        for mailbox in mailbox_list:
            print(mailbox.decode())

    def read_emails(self, folder: str = 'INBOX', imap_keyword: str = "UNSEEN"):
        self.client.select(folder)
        _, data = self.client.uid('search', None, imap_keyword)
        
        # get email uid list
        email_list = data[0].split()
        self.logger.info(f"got {len(email_list)} emails")
        email_list.reverse()
        for uid in email_list:
            if self.check_email_saved(uid):
                self.logger.info(f"email uid {uid} already saved")
            else:
                self.read_and_save_email(uid)
                self.logger.info(f"email uid {uid} saved")

    def read_and_save_email(self, uid: str):
        message_parts = "(BODY.PEEK[])"
        _, email_data = self.client.uid('fetch', uid, message_parts)
        mail = mailparser.parse_from_bytes(email_data[0][1])
        self.logger.info(f"got email subject [{mail.subject}]")
        self.save_email(mail)

    def get_local_dir_name(self, mail: mailparser.MailParser) -> str:
        dir =  f"{self.config.get('LOCAL_DIR')}/{self.config.get('EMAIL_ADDRESS')}"
        name = f"{mail.subject}__{mail.date}"
        name = hashlib.md5(name.encode('utf-8')).hexdigest()
        return f"{dir}/{name}"

    def check_email_saved(self, uid: str):
        message_parts = "(BODY[HEADER])"
        _, email_data = self.client.uid('fetch', uid, message_parts)
        mail = mailparser.parse_from_bytes(email_data[0][1])
        self.logger.info(f"[{uid}]check email subject [{mail.subject}]")
        dir = self.get_local_dir_name(mail)
        self.logger.info(f"check email saved {dir}")
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
                    self.logger.info(f"save email image {filename} success")

    # save email body images(html content)
    def save_body_images(self, html_content: str, email_dir: str):
        # get all image urls
        soup = BeautifulSoup(html_content, 'html.parser')
        img_tags = soup.find_all('img')
        img_urls = [img['src'] for img in img_tags if 'src' in img.attrs]
        self.logger.info(f'Found {len(img_urls)} images in email body')

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
                self.logger.info(f'Downloaded {img_url} to {img_filename}')
            else:
                self.logger.info(f'Failed to download {img_url}')

    # save email content to local dir
    def save_email(self, mail: mailparser.MailParser):
        dir = f"{self.config.get('LOCAL_DIR')}/{self.config.get('EMAIL_ADDRESS')}"
        if not os.path.exists(dir):
            os.makedirs(dir)
        email_dir = self.get_local_dir_name(mail)
        self.logger.info(f"save email to {email_dir}")
        if not os.path.exists(email_dir):
            os.makedirs(email_dir)
        with open(f"{email_dir}/email.txt", "w") as f:
            f.write(mail.body)
        with open(f"{email_dir}/meta.json", "w", encoding='utf-8') as f:
            mail_dict = json.loads(mail.mail_json)
            if 'body' in mail_dict:
                del mail_dict['body']
            json.dump(mail_dict, f, ensure_ascii=False, indent=4)
            self.logger.info(f"save email meta info {f.name}")
        
        self.save_email_attachment(mail, email_dir)
        self.save_body_images(mail.body, f"{email_dir}/body_image")



from . import AIStorage, KnowledgeBase

# define singleton class knowledge pipline
class KnowledgePipline:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = KnowledgePipline()
            cls._instance.__singleton_init__()

        return cls._instance

    def __singleton_init__(self) -> None:
        self.knowledge_base = KnowledgeBase()

    @classmethod
    def declare_user_config(cls):
        user_config = AIStorage.get_instance().get_user_config()
        user_config.add_user_config("email_spiders","email addresses to build knowledge base",True,None,"list")
        user_config.add_user_config("personal_dirs", "personal directories to build knowledge base", True, None, "list")

    def add_email_address(self, ) -> None:
        pass
