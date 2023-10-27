
class KnowledgeEmailSource:
    def __init__(self, config:dict): 
        self.config = config
        self.config["type"] = "email"
    
    def id(self):
        return self.config["address"]

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
        return os.path.abspath(f"{user_data_dir}/knowledge/email")    

    async def run_once(self):
        # read config from toml file
        # and read from config config.local.toml if exists (config.local.toml is ignored by git)
        logging.debug(f"knowledge email source {self.id()} run once")
        filter = "ALL"  
        self.client = self.email_client()
        await self.read_emails(imap_keyword=filter)

    def email_client(self) -> imaplib.IMAP4_SSL:
        logging.info(f"read email config from {self.config.get('imap_server')}")
        client = imaplib.IMAP4_SSL(
            host=self.config.get('imap_server'), 
            port=self.config.get('imap_port')
        )
        client.login(self.config.get('address'), self.config.get('password'))
        return client

    async def read_emails(self, folder: str = 'INBOX', imap_keyword: str = "UNSEEN"):
        journal_client = KnowledgeJournalClient()
        latest_journal = journal_client.latest_journal(self.id())
        latest_uid = 0 if latest_journal is None else int(latest_journal.item_id)
        self.client.select(folder)
        _, data = self.client.uid('search', None, imap_keyword)
        
        # get email uid list
        email_list = data[0].split()
        logging.info(f"got {len(email_list)} emails")
        journal_client = KnowledgeJournalClient()
        for uid in email_list:
            _uid = int.from_bytes(uid)
            if _uid > latest_uid:
                email_dir = self.check_email_saved(uid)
                if email_dir is not None:
                    logging.info(f"email uid {uid} already saved")
                else:
                    email_dir = self.read_and_save_email(uid)
                    logging.info(f"email uid {uid} saved")
                email_object = EmailObjectBuilder({}, email_dir).build()
                await KnowledgeBase().insert_object(email_object)
                journal_client.insert(KnowledgeJournal("email", self.id(), str(int.from_bytes(uid)), str(email_object.calculate_id())))


    def read_and_save_email(self, uid: str) -> str:
        message_parts = "(BODY.PEEK[])"
        _, email_data = self.client.uid('fetch', uid, message_parts)
        mail = mailparser.parse_from_bytes(email_data[0][1])
        logging.info(f"got email subject [{mail.subject}]")
        self.save_email(mail)
        return self.get_local_dir_name(mail)

    def get_local_dir_name(self, mail: mailparser.MailParser) -> str:
        dir =  f"{self.local_root()}/{self.config.get('address')}"
        name = f"{mail.subject}__{mail.date}"
        name = hashlib.md5(name.encode('utf-8')).hexdigest()
        return f"{dir}/{name}"

    def check_email_saved(self, uid: str) -> str:
        message_parts = "(BODY[HEADER])"
        _, email_data = self.client.uid('fetch', uid, message_parts)
        mail = mailparser.parse_from_bytes(email_data[0][1])
        logging.info(f"[{uid}]check email subject [{mail.subject}]")
        dir = self.get_local_dir_name(mail)
        logging.info(f"check email saved {dir}")
        file = f"{dir}/email.txt"
        if os.path.exists(file):
            return dir
        return None

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

        name_count = 0
        
        if not os.path.exists(email_dir):
            os.makedirs(email_dir)

        for img_url in img_urls:
            # keep the original image filename(last of url)
            ext = img_url.split('/')[-1].split('.')[-1]
            img_filename = os.path.join(email_dir, f"{name_count}.{ext}")
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

    # save email content to local dir
    def save_email(self, mail: mailparser.MailParser):
        dir = f"{self.local_root()}/{self.config.get('address')}"
        if not os.path.exists(dir):
            os.makedirs(dir)
        email_dir = self.get_local_dir_name(mail)
        logging.info(f"save email to {email_dir}")
        if not os.path.exists(email_dir):
            os.makedirs(email_dir)
        with open(f"{email_dir}/email.txt", "w", encoding='utf-8') as f:
            # soup = BeautifulSoup(mail.body, 'html.parser')
            f.write(mail.body)
        with open(f"{email_dir}/meta.json", "w", encoding='utf-8') as f:
            mail_dict = json.loads(mail.mail_json)
            if 'body' in mail_dict:
                del mail_dict['body']
            json.dump(mail_dict, f, ensure_ascii=False, indent=4)
            logging.info(f"save email meta info {f.name}")
        
        self.save_email_attachment(mail, email_dir)
        self.save_body_images(mail.body, f"{email_dir}/body_image")