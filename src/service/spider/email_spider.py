import imaplib
import os
import toml
import logging
import mailparser
import hashlib
import json
import base64

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

if __name__ == "__main__":
    spider = EmailSpider()
    folder = 'INBOX'
    imap_keyword = "ALL"
    spider.read_emails(folder, imap_keyword)