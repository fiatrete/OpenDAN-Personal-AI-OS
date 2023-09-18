import logging
import threading
import asyncio
import uuid

from typing import Callable

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .tunnel import AgentTunnel
from .contact_manager import ContactManager
from .agent_message import AgentMsg

logger = logging.getLogger(__name__)

class TelegramTunnel(AgentTunnel):

    @classmethod
    def register_to_loader(cls):
        async def load_tg_tunnel(config:dict) -> AgentTunnel:
            result_tunnel = TelegramTunnel("")
            if await result_tunnel.load_from_config(config):
                return result_tunnel
            else:
                return None
            
        AgentTunnel.register_loader("TelegramTunnel",load_tg_tunnel)

        
    async def load_from_config(self,config:dict)->bool:
        self.tg_token = config["token"]
        self.target_id = config["target"]
        self.tunnel_id = config["tunnel_id"]
        self.type = "TelegramTunnel"
        return True

    def dump_to_config(self) -> dict:
        pass

    def __init__(self,tg_token:str) -> None:
        super().__init__()
        self.is_start = False
        self.tg_token = tg_token
        #self.tunnel_id = "tg_tunnel#" + self.app.bot.id

    async def start(self) -> bool:
        if self.is_start:
            logger.warning(f"tunnel {self.tunnel_id} is already started")
            return False
        self.is_start = True   

        self.app:Application = Application.builder().token(self.tg_token).build()
        self.app.add_handler(MessageHandler(filters.TEXT, self.on_message))

        def _run_app():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.app.run_polling(allowed_updates=Update.ALL_TYPES)

        self.poll_thread = threading.Thread(target=_run_app)
        self.poll_thread.start()
        return True

    async def close(self) -> None:
        pass

    async def _process_message(self, msg: AgentMsg) -> None:
        logger.warn(f"process message {msg.msg_id} from {msg.sender} to {msg.target}")

    async def conver_tg_msg_to_agent_msg(self,update:Update) -> AgentMsg:
        agent_msg = AgentMsg()
        agent_msg.topic = "_telegram"
        agent_msg.msg_id = "tg_msg#" + str(update.message.message_id) + "#" + uuid.uuid4().hex
        agent_msg.target = self.target_id
        agent_msg.body = update.message.text
        agent_msg.create_time = update.message.date.timestamp()
        #if update.message.photo is not None:
        #    agent_msg.body_mime = "image"
        #    agent_msg.body = update.message.photo[-1].get_file().download()
        return agent_msg



    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        cm = ContactManager.get_instance()
        reomte_user_name = f"{update.effective_user.id}@telegram"
        #contact = cm.get_by_name(update.effective_user.username)
        #if contact is not None:
        #    reomte_user_name = contact.get_name()
        #if contact is None:
        #    update.message.reply_text(f"{self.target_id} process message error, unknown user!")
        #if not contact.is_zone_owner():
        #    update.message.reply_text(f"{self.target_id} process message error, you are not my owner!")

        agent_msg = await self.conver_tg_msg_to_agent_msg(update)
        agent_msg.sender = reomte_user_name
        self.ai_bus.register_message_handler(reomte_user_name, self._process_message)
        resp_msg = await self.ai_bus.send_message(agent_msg)
        if resp_msg is None:
            await update.message.reply_text(f"{self.target_id} process message error")
        else:
            if resp_msg.body_mime is None:
                await update.message.reply_text(resp_msg.body)
            else:
                if resp_msg.body_mime.startswith("image"):
                    photo_file = open(resp_msg.body,"rb")
                    if photo_file:
                        await update.message.reply_photo(resp_msg.body)
                    else:
                        await update.message.reply_text(resp_msg.body)
                else:
                    await update.message.reply_text(resp_msg.body)
            
        
        