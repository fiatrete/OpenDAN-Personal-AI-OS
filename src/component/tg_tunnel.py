import datetime
import logging
import os.path
import threading
import asyncio
import uuid
import time
import aiofiles

from telegram import Update,Message
from telegram import Bot
from telegram.ext import Updater
from telegram.error import Forbidden, NetworkError

from aios import ObjectType, KnowledgeStore,AgentTunnel,AIStorage,ContactManager,Contact,FamilyMember,AgentMsg,AgentMsgType

logger = logging.getLogger(__name__)

class TelegramTunnel(AgentTunnel):
    all_bots = {}
    default_chatid = {}
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
        self.type = "TelegramTunnel"
        self.tg_token = config["token"]
        self.target_id = config["target"]
        self.tunnel_id = config["tunnel_id"]
        if config.get("allow") is not None:
            self.allow_group = config["allow"]

        return True

    def dump_to_config(self) -> dict:
        pass

    def __init__(self,tg_token:str) -> None:
        super().__init__()
        self.is_start = False
        self.tg_token = tg_token
        self.bot:Bot = None
        self.update_queue = None
        self.allow_group = "contact"
        self.in_process_tg_msg = {}
        self.chatid_record = {}
        self.telegram_cache = os.path.join(AIStorage.get_instance().get_myai_dir(), "telegram")
        if not os.path.exists(self.telegram_cache):
            os.makedirs(self.telegram_cache)

    async def _do_process_raw_message(self,bot: Bot, update_id: int) -> int:
        # Request updates after the last update_id
        updates = await bot.get_updates(offset=update_id, timeout=10, allowed_updates=Update.ALL_TYPES)
        for update in updates:
            next_update_id = update.update_id + 1

            if update.message and (update.message.text or (update.message.photo and len(update.message.photo) > 0) or update.message.video):

                await self.on_message(bot,update)
            return next_update_id

        return update_id

    async def start(self) -> bool:
        if self.is_start:
            logger.warning(f"tunnel {self.tunnel_id} is already started")
            return False
        self.is_start = True
        logger.info(f"tunnel {self.tunnel_id} is starting...")

        self.bot = Bot(self.tg_token)
        self.bot_username = (await self.bot.get_me()).username
        self.update_queue = asyncio.Queue()
        self.bot_updater = Updater(self.bot,update_queue=self.update_queue)

        TelegramTunnel.all_bots[self.target_id] = self.bot

        async def _run_app():
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
                except  Exception as e:
                    logger.error(f"tg_tunnel error:{e}")
                    logger.exception(e)
                    await asyncio.sleep(1)



        asyncio.create_task(_run_app())
        logger.info(f"tunnel {self.tunnel_id} started.")
        return True

    async def close(self) -> None:
        pass

    async def _process_message(self, msg: AgentMsg) -> bool:
       logger.warn(f"tg_tunnel process message {msg.msg_id} from agent {msg.sender} to human {msg.target}")

    # async def _process_message(self, msg: AgentMsg) -> bool:
    #     logger.info(f"tg_tunnel process message {msg.msg_id} from agent {msg.sender} to human {msg.target}")
    #     cm = ContactManager.get_instance()
    #     contact = cm.find_contact_by_name(msg.target)
    #     bot = TelegramTunnel.all_bots.get(msg.sender)
    #     chatid_index = f"{self.target_id}#{msg.target}"
    #     chatid = TelegramTunnel.default_chatid.get(chatid_index)
    #     if chatid is None:
    #         logger.warning(f"tg_tunnel process message {msg.msg_id} from agent {msg.sender} to human {msg.target} failed! chatid not found!")
    #         return None

    #     if bot is None:
    #         logger.warning(f"tg_tunnel process message {msg.msg_id} from agent {msg.sender} to human {msg.target} failed! bot not found!")
    #         return None

    #     if contact:
    #         if contact.telegram:
    #             await bot.send_message(chat_id=chatid,text=msg.body)
    #             logging.info(f"tg_tunnel send message {msg.msg_id} from agent {msg.sender} to human {msg.target} @ chatid:{chatid}success!")
    #             return None

    #     logger.warning(f"tg_tunnel process message {msg.msg_id} from agent {msg.sender} to human {msg.target} failed! contact not found!")
    #     return None

    async def post_message(self, msg: AgentMsg) -> None:
        chatid = self.chatid_record.get(msg.target)
        if chatid:
            # TODO: support image and audio
            await self.bot.send_message(chat_id=chatid,text=msg.body)
            logging.info(f"tg_tunnel send message {msg.msg_id} from agent {msg.sender} to human {msg.target} @ chatid:{chatid}success!")
        else:
            logger.warning(f"tg_tunnel process message {msg.msg_id} from agent {msg.sender} to human {msg.target} failed! chatid not found!")

    def get_cache_path(self) -> str:
        today = datetime.datetime.today()
        path = os.path.join(self.telegram_cache, str(today.year), str(today.month))
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    async def conver_tg_msg_to_agent_msg(self,message:Message) -> AgentMsg:
        agent_msg = AgentMsg()
        agent_msg.topic = "_telegram"
        agent_msg.msg_id = "tg_msg#" + str(message.message_id) + "#" + uuid.uuid4().hex
        agent_msg.target = self.target_id
        if message.text is not None:
            agent_msg.body = message.text
        elif message.photo is not None and len(message.photo) > 0:
            photo_files = []
            photo_file = await message.photo[-1].get_file()
            ext = photo_file.file_path.rsplit(".")[-1]
            file_path = os.path.join(self.get_cache_path(), photo_file.file_id + f".{ext}")
            await photo_file.download_to_drive(file_path)
            photo_files.append(file_path)
            agent_msg.body = agent_msg.create_image_body(photo_files, message.caption)
            agent_msg.body_mime = f"image/{ext}"
        elif message.video is not None:
            video_file = await message.video.get_file()
            ext = video_file.file_path.rsplit(".")[-1]
            file_path = os.path.join(self.get_cache_path(), video_file.file_id + f".{ext}")
            await video_file.download_to_drive(file_path)
            agent_msg.body = agent_msg.create_video_body(file_path, message.caption)
            agent_msg.body_mime = f"video/{ext}"

        agent_msg.create_time = time.time()
        messag_type = message.chat.type
        if messag_type == "supergroup" or messag_type == "group":
            agent_msg.target = f"tg_group{message.chat_id}"
            agent_msg.msg_type = AgentMsgType.TYPE_GROUPMSG
            agent_msg.mentions = []
        else:
            agent_msg.msg_type = AgentMsgType.TYPE_MSG
            agent_msg.mentions = []

        if message.entities:
            for entity in message.entities:
                if entity.type == 'mention':
                    mention = message.text[entity.offset:entity.offset+entity.length]
                    if mention == '@' + self.bot_username:
                        agent_msg.mentions.append(self.target_id)
                    else:
                        agent_msg.mentions.append(mention)

        if message.caption_entities:
            for entity in message.caption_entities:
                if entity.type == 'mention':
                    mention = message.caption[entity.offset:entity.offset+entity.length]
                    if mention == '@' + self.bot_username:
                        agent_msg.mentions.append(self.target_id)
                    else:
                        agent_msg.mentions.append(mention)

        return agent_msg

    def is_bot_mentioned(self,message:Message):
        if message.entities:
            for entity in message.entities:
                if entity.type == 'mention':
                    mention = message.text[entity.offset:entity.offset+entity.length]
                    if mention == '@' + self.bot_username:
                        return True

        if message.caption_entities:
            for entity in message.caption_entities:
                if entity.type == 'mention':
                    mention = message.caption[entity.offset:entity.offset+entity.length]
                    if mention == '@' + self.bot_username:
                        return True

        return False

    async def on_message(self, bot:Bot, update: Update) -> None:
        message = update.message
        logger.info(f"on_message: {message.message_id} from {message.from_user.username} ({update.effective_user.username}) to {message.chat.title}({message.chat.id})")
        if update.effective_user.is_bot:
            logger.warning(f"ignore message from telegram bot {update.effective_user.id}")
            return None

        if self.in_process_tg_msg.get(update.message.message_id) is not None:
            logger.warning(f"ignore message from telegram bot {update.effective_user.id}")
            return None

        self.in_process_tg_msg[update.message.message_id] = True

        agent_msg = await self.conver_tg_msg_to_agent_msg(message)
        cm : ContactManager = ContactManager.get_instance()
        reomte_user_name = f"{update.effective_user.id}@telegram"

        contact : Contact = cm.find_contact_by_telegram(update.effective_user.username)
        if contact is None:
            contact = cm.find_contact_by_telegram(str(update.effective_user.id))

        if contact is not None:
            reomte_user_name = contact.name

            #TelegramTunnel.default_chatid[f"{self.target_id}#{reomte_user_name}"] = update.effective_chat.id
            if not contact.is_family_member:
                if self.allow_group != "contact" and self.allow_group !="guest":
                    await update.message.reply_text(f"You're not supposed to talk to me! Please contact my father~")
                    return

        else:
            if self.allow_group != "guest":
                await update.message.reply_text(f"The current Telegram account is not in the contact list. If you want to receive a reply, you can add the configuration in the contacts.toml file or switch tunnel to guest mode.")
                return

            if cm.is_auto_create_contact_from_telegram:
                contact_name = update.effective_user.first_name
                if update.effective_user.last_name is not None:
                    contact_name += " " + update.effective_user.last_name

                contact = Contact(contact_name)
                contact.telegram = update.effective_user.username if update.effective_user.username is not None else str(update.effective_user.id)
                contact.added_by = self.target_id
                cm.add_contact(contact.name, contact)
                reomte_user_name = contact.name

        if contact is not None:
            contact.set_active_tunnel(self.target_id,self)
            self.chatid_record[reomte_user_name] = update.effective_chat.id
            self.ai_bus.register_message_handler(reomte_user_name,contact._process_msg)

        agent_msg.sender = reomte_user_name
        logger.info(f"process message {agent_msg.msg_id} from {agent_msg.sender} to {agent_msg.target}")
        if agent_msg.msg_type == AgentMsgType.TYPE_GROUPMSG:
            self.ai_bus.register_message_handler(agent_msg.target, self._process_message)
            resp_msg = await self.ai_bus.send_message(agent_msg,self.target_id,agent_msg.target)
        else:
            #self.ai_bus.register_message_handler(reomte_user_name, self._process_message)
            resp_msg = await self.ai_bus.send_message(agent_msg)
        #await bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")



        if resp_msg is None:
            await update.message.reply_text(f"System Error: Timeout,{self.target_id}  no resopnse! Please check logs/aios.log for more details!")
        else:
            if resp_msg.body_mime is None:
                if resp_msg.body is None:
                    return

                if len(resp_msg.body) < 1:
                    await update.message.reply_text("")
                    return

                knowledge_object = KnowledgeStore().parse_object_in_message(resp_msg.body)
                if knowledge_object is not None:
                    if knowledge_object.get_object_type() == ObjectType.Image:
                        image = KnowledgeStore().bytes_from_object(knowledge_object)
                        try:
                            async with aiofiles.open("tg_send_temp.png", mode='wb') as local_file:
                                if local_file:
                                    await local_file.write(image)
                                    await update.message.reply_photo("tg_send_temp.png")
                        except Exception as e:
                            logger.error(f"save image error: {e}")
                        return
                else:
                    pos = resp_msg.body.find("audio file")
                    if pos != -1:
                        audio_file = resp_msg.body[pos+11:].strip()
                        if audio_file.startswith("\""):
                            audio_file = audio_file[1:-1]
                        await update.message.reply_voice(audio_file)
                        return
                await update.message.reply_text(resp_msg.body)
            else:
                if resp_msg.body_mime.startswith("image"):
                    photo_file = open(resp_msg.body,"rb")
                    if photo_file:
                        await update.message.reply_photo(resp_msg.body)
                        photo_file.close()
                    else:
                        await update.message.reply_text(resp_msg.body)

                else:
                    await update.message.reply_text(resp_msg.body)


