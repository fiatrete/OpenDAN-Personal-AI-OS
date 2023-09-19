import logging
import threading
import asyncio
import uuid
import time

from typing import Callable

from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from telegram import Bot
from telegram.ext import Updater
from telegram.error import Forbidden, NetworkError

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
        #self.bot:Bot = None
        #self.update_queue = None
        #self.tunnel_id = "tg_tunnel#" + self.app.bot.id

    async def _do_process_raw_message(self,bot: Bot, update_id: int) -> int:
        """Echo the message the user sent."""
        # Request updates after the last update_id
        updates = await bot.get_updates(offset=update_id, timeout=10, allowed_updates=Update.ALL_TYPES)
        for update in updates:
            next_update_id = update.update_id + 1

            # your bot can receive updates without messages
            # and not all messages contain text
            if update.message and update.message.text:
                # Reply to the message
                #logger.info("Found message %s!", update.message.text)
                await self.on_message(update)
            return next_update_id
        
        return update_id

    async def start(self) -> bool:
        if self.is_start:
            logger.warning(f"tunnel {self.tunnel_id} is already started")
            return False
        self.is_start = True   
        logger.warning(f"tunnel {self.tunnel_id} is starting...")

        self.bot = Bot(self.tg_token)
        self.update_queue = asyncio.Queue()
        self.bot_updater = Updater(self.bot,update_queue=self.update_queue)
       
        #self.app:Application = Application.builder().token(self.tg_token).build()
        
        #self.app.add_handler(MessageHandler(filters.TEXT, self.on_message))

        async def _run_app():
            #loop = asyncio.new_event_loop()
            #asyncio.set_event_loop(loop)
            #self.app.run_polling(allowed_updates=Update.ALL_TYPES)
            
            try:
                update_id = (await self.bot.get_updates())[0].update_id
            except IndexError:
                update_id = None

            #logger.info("listening for new messages...")
            while True:
                try:
                    update_id = await self._do_process_raw_message(self.bot, update_id)
                except NetworkError:
                    await asyncio.sleep(1)
                except Forbidden:
                    # The user has removed or blocked the bot.
                    update_id += 1

        #self.poll_thread = threading.Thread(target=_run_app)
        #self.poll_thread.start()
        asyncio.create_task(_run_app())
        logger.warning(f"tunnel {self.tunnel_id} started.")
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
        agent_msg.create_time = time.time()
        #if update.message.photo is not None:
        #    agent_msg.body_mime = "image"
        #    agent_msg.body = update.message.photo[-1].get_file().download()
        return agent_msg



    async def on_message(self, update: Update) -> None:
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
        #await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="thinking")
        resp_msg = await self.ai_bus.send_message(agent_msg)
        logger.info(f"process message {agent_msg.msg_id} from {agent_msg.sender} to {agent_msg.target}")
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
            
        
        