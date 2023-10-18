import asyncio
import aiosmtplib
import aioimaplib
import email
from email.header import decode_header
import mailparser
import logging
import time
import datetime
from .tunnel import AgentTunnel
from .agent_base import AgentMsg

from email.message import EmailMessage

logger = logging.getLogger(__name__)

class EmailTunnel(AgentTunnel):
    @classmethod
    def register_to_loader(cls):
        async def load_email_tunnel(config:dict) -> AgentTunnel:
            result_tunnel = EmailTunnel()
            if await result_tunnel.load_from_config(config):
                return result_tunnel
            else:
                return None
            
        AgentTunnel.register_loader("EmailTunnel",load_email_tunnel)

    async def load_from_config(self,config:dict)->bool:
        self.target_id = config["target"]
        self.tunnel_id = config["tunnel_id"]

        self.type = "TelegramTunnel"
        self.email = config["email"]
        self.imap_server = config["imap"]
        s = self.imap_server.split(":")
        if len(s) == 2:
            self.imap_server = s[0]
            self.imap_port = int(s[1])

        self.smtp_server = config["smtp"]   
        s = self.smtp_server.split(":")
        if len(s) == 2:
            self.smtp_server = s[0]
            self.smtp_port = int(s[1])

        self.login_user = config["user"]
        self.login_password = config["password"]
        self.folder = config["folder"]
        self.check_interval = config["interval"]

        return True  
    
    def __init__(self) -> None:
        super().__init__()
        self.is_start = False
        self.read_email = {}

    async def on_new_email(self,mail:mailparser.MailParser) -> None:
        remote_email_addr = mail.from_[0][1]
        remote_user_name = remote_email_addr.split("@")[0] 
        agent_msg = self.conver_mail_to_agent_msg(mail)
        agent_msg.sender = remote_user_name
        agent_msg.target = self.target_id
        self.ai_bus.register_message_handler(remote_user_name, self._process_message)

        resp_msg = await self.ai_bus.send_message(agent_msg)
        if resp_msg is None:
            await self.reply_email(remote_email_addr,"Sorry, I can't understand your message","")
        else:
            if resp_msg.body_mime is None:
                await self.reply_email(remote_email_addr,"result",resp_msg.body)

    async def reply_email(self,target_email:str,title:str,msg:str) -> None:
        email_msg = EmailMessage()
        email_msg['Subject'] = f"Reply: {title}"
        email_msg['From'] = self.email
        email_msg['To'] = target_email
        email_msg.set_content(msg)

        await aiosmtplib.send(
            email_msg,
            hostname = self.smtp_server,
            port=self.smtp_port,
            username=self.login_user,
            password=self.login_password,
            )



    def conver_mail_to_agent_msg(self,mail:mailparser.MailParser) -> AgentMsg:
        msg = AgentMsg()
        msg.set("",self.target_id,mail.text_plain[0])
        msg.topic = "email"
        return msg

    async def check_email(self) -> None:
        self.last_check_num = 0
        self.last_check_time = datetime.datetime.now()
        while True:
            if self.is_start == False:
                return
            
            await asyncio.sleep(self.check_interval)
            imap_client = aioimaplib.IMAP4_SSL(host=self.imap_server,port=self.imap_port)
            await imap_client.wait_hello_from_server()
            await imap_client.login(self.login_user, self.login_password)

            date_since = self.last_check_time.strftime("%d-%b-%Y")
            
            await imap_client.select(self.folder)
            status, messages = await imap_client.search('UNSEEN',charset='US-ASCII')
            self.last_check_time = datetime.datetime.now()
            if status == "OK":
                message_numbers = messages[0].split()
                for num in message_numbers:
                    num = int(num)
                    if self.read_email.get(num) is not None:
                        continue
                    
                    status, email_data = await imap_client.fetch(str(num), "(RFC822)")
                    if status == "OK":
                        #r = email.message_from_bytes(email_data[1])
                        mail = mailparser.parse_from_bytes(email_data[1])
                        self.read_email[num] = mail
                        await self.on_new_email(mail)

            await imap_client.logout()

    async def start(self) -> bool:
        if self.is_start:
            logger.warning(f"tunnel {self.tunnel_id} is already started")
            return False
        self.is_start = True   

        asyncio.create_task(self.check_email())
        return True

    async def close(self) -> None:
        self.is_start = False

    async def _process_message(self, msg: AgentMsg) -> None:
        logger.warn(f"process message {msg.msg_id} from {msg.sender} to {msg.target}")
