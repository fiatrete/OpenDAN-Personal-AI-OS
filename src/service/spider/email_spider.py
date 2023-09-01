import imaplib
import os
import toml
import logging
import mailparser
import hashlib
import json

# logger config
logger = logging.getLogger('email spider')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s [%(name)s] [%(levelname)s] %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

# read config from toml file
# and read from config config.local.toml if exists (config.local.toml is ignored by git)
config = toml.load('./rootfs/email/config.toml')
if os.path.exists('./rootfs/email/config.local.toml'):
    config = toml.load('./rootfs/email/config.local.toml')


# create email client
def email_client() -> imaplib.IMAP4_SSL:
    logger.info(f"read email config from {config.get('EMAIL_IMAP_SERVER')}")
    client = imaplib.IMAP4_SSL(config.get('EMAIL_IMAP_SERVER'))
    client.login(config.get('EMAIL_ADDRESS'), config.get('EMAIL_PASSWORD'))
    return client

def list_box(mail:  imaplib.IMAP4_SSL):
    _, mailbox_list = mail.list()
    for mailbox in mailbox_list:
        print(mailbox.decode())
    
def read_emails(client: imaplib.IMAP4_SSL, folder: str = 'INBOX', imap_keyword: str = "UNSEEN"):
    client.select(folder)
    _, data = client.uid('search', None, imap_keyword)
    # get email uid list
    email_list = data[0].split()
    logger.info(f"got {len(email_list)} emails")
    for uid in email_list:
        logger.info(f"read email uid {uid}")
        if check_email_saved(client, uid):
            logger.info(f"email uid {uid} already saved")
            continue
        else:
            read_and_save_email(client, uid)
            logger.info(f"email uid {uid} saved")


def read_and_save_email(client: imaplib.IMAP4_SSL, uid: str):
    message_parts = "(BODY.PEEK[])"
    _, email_data = client.uid('fetch', uid, message_parts)
    mail = mailparser.parse_from_bytes(email_data[0][1])
    logger.info(f"got email subject [{mail.subject}]")
    save_email(mail)

def get_local_dir_name(mail: mailparser.MailParser) -> str:
    dir =  f"{config.get('LOCAL_DIR')}/{config.get('EMAIL_ADDRESS')}"
    name = f"{mail.subject}__{mail.date}"
    name = hashlib.md5(name.encode('utf-8')).hexdigest()
    return f"{dir}/{name}"


# check only need to check email header, not need to download email body
def check_email_saved(client: imaplib.IMAP4_SSL, uid: str):
    message_parts = "(BODY[HEADER])"
    _, email_data = client.uid('fetch', uid, message_parts)
    mail = mailparser.parse_from_bytes(email_data[0][1])
    logger.info(f"check email subject [{mail.subject}]")
    dir = get_local_dir_name(mail)
    logger.info(f"check email saved {dir}")
    file = f"{dir}/email.txt"
    if os.path.exists(file):
        return True
    return False


# save email to local file by each folder
def save_email(mail: mailparser.MailParser):
    # create email account dir
    dir = f"{config.get('LOCAL_DIR')}/{config.get('EMAIL_ADDRESS')}"
    if not os.path.exists(dir):
        os.makedirs(dir)
    # create email local dir
    email_dir = get_local_dir_name(mail)
    logger.info(f"save email to {email_dir}")
    if not os.path.exists(email_dir):
        os.makedirs(email_dir)
    
    # save email content and meta info
    with open(f"{email_dir}/email.txt", "w") as f:
        f.write(mail.body)
    with open(f"{email_dir}/meta.json", "w", encoding='utf-8') as f:
        mail_dict = json.loads(mail.mail_json)
        if 'body' in mail_dict:
            del mail_dict['body']
        json.dump(mail_dict, f, ensure_ascii=False, indent=4)
        logger.info(f"save email meta info {f.name}")



if __name__ == "__main__":
    mail = email_client()
    folder = 'INBOX'
    # imap_keyword = "UNSEEN"
    imap_keyword = "ALL"
    read_emails(mail, folder, imap_keyword)
