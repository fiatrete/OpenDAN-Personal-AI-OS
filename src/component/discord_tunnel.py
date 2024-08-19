import asyncio
import datetime
import time
import logging
import os
import re
import uuid
import aiofiles
from urllib.parse import urlparse
from typing import Optional

#from aios import KnowledgeStore, ObjectType
from aios.frame.tunnel import AgentTunnel
from aios.proto.agent_msg import AgentMsg, AgentMsgType
import discord

from aios.storage.storage import AIStorage

logger = logging.getLogger(__name__)


IMAGE_FORMATS = ["jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff", "tif"]
VIDEO_FORMATS = ["mp4", "avi", "mov", "wmv", "flv", "mkv", "webm"]
AUDIO_FORMATS = ["mp3", "wav", "ogg", "flac", "aac", "m4a", "wma", "ape", "alac", "opus", "oga"]


class DiscordTunnel(AgentTunnel):
    target_id: str
    type: str
    tunnel_id: str

    def __init__(self, token: Optional[str] = None):
        super().__init__()
        self.token = token
        self.client: discord.Client = None

        self.discord_cache = os.path.join(AIStorage.get_instance().get_myai_dir(), "discord")
        if not os.path.exists(self.discord_cache):
            os.makedirs(self.discord_cache)

    @classmethod
    def register_to_loader(cls):
        async def load_discord_tunnel(config: dict) -> AgentTunnel:
            result_tunnel = DiscordTunnel()
            if await result_tunnel.load_from_config(config):
                return result_tunnel
            else:
                return None

        AgentTunnel.register_loader("DiscordTunnel", load_discord_tunnel)

    async def load_from_config(self, config: dict) -> bool:
        self.type = "DiscordTunnel"
        self.token = config["token"]
        self.target_id = config["target"]
        self.tunnel_id = config["tunnel_id"]
        return True

    def get_cache_path(self) -> str:
        today = datetime.datetime.today()
        path = os.path.join(self.discord_cache, str(today.year), str(today.month))
        if not os.path.exists(path):
            os.makedirs(path)
        return path


    def post_message(self, msg: AgentMsg) -> None:
        if self.client is None:
            logger.error("DiscordTunnel is not started")
            return

        logger.warn("post_message not implemented")

    async def start(self) -> bool:
        if self.client is not None:
            logger.warn("DiscordTunnel is already started")
            return False

        if self.token is None:
            self.token = os.environ.get("DISCORD_TOKEN")
            if self.token is None:
                raise ValueError("Discord token must be provided")

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            print(f"Logged in as {self.client.user}")

        @client.event
        async def on_message(message: discord.Message):
            logger.info(f"Message from {message.author}: {message.content}")
            if message.author == self.client.user:
                return

            content = re.sub("<@.+>", "", message.content).strip()

            attach_type = None
            images = []
            ext = None
            video_file = None
            audio_file = None
            if message.attachments is not None and len(message.attachments) > 0:
                for attachment in message.attachments:
                    logger.info(f"Attachment: {attachment.url}")
                    url = urlparse(attachment.url)
                    ext = url.path.rsplit(".")[-1]

                    file_path = os.path.join(self.get_cache_path(), attachment.filename)
                    with open(file_path, "wb") as f:
                        await attachment.save(f)

                    if ext in IMAGE_FORMATS:
                        if attach_type is None:
                            attach_type = "image"
                        elif attach_type != "image":
                            break
                        images.append(file_path)
                    elif ext in VIDEO_FORMATS:
                        if attach_type is None:
                            attach_type = "video"
                        video_file = file_path
                        break
                    elif ext in AUDIO_FORMATS:
                        if attach_type is None:
                            attach_type = "audio"
                        audio_file = file_path
                        break

            agent_msg = AgentMsg()
            agent_msg.topic = "_discord"
            agent_msg.msg_id = "discord_msg#" + str(message.id) + "#" + uuid.uuid4().hex
            agent_msg.target = self.target_id
            agent_msg.create_time = time.time()
            agent_msg.sender = message.author.name
            self.ai_bus.register_message_handler(agent_msg.sender, self._process_message)

            if len(message.channel.members) > 2:
                if self.client.user not in message.mentions:
                    agent_msg.msg_type = AgentMsgType.TYPE_GROUP_MSG

            if attach_type is None:
                agent_msg.body = content
            elif attach_type == "image":
                agent_msg.body = agent_msg.create_image_body(images, content)
                agent_msg.body_mime = f"image/{ext}"
            elif attach_type == "video":
                agent_msg.body = agent_msg.create_video_body(video_file, content)
                agent_msg.body_mime = f"video/{ext}"
            elif attach_type == "audio":
                agent_msg.body = agent_msg.create_audio_body(audio_file, content)
                agent_msg.body_mime = f"audio/{ext}"

            resp_msg: AgentMsg = await self.ai_bus.send_message(agent_msg)
            if resp_msg is None:
                await message.channel.send(f"System Error: Timeout,{self.target_id}  no resopnse! Please check logs/aios.log for more details!")
            else:
                if resp_msg.body_mime is None:
                    if resp_msg.body is None:
                        return

                    if len(resp_msg.body) < 1:
                        return

                    # knownledge_object = KnowledgeStore().parse_object_in_message(resp_msg.body)
                    # if knownledge_object is not None:
                    #     if knownledge_object.get_object_type() == ObjectType.Image:
                    #         image = KnowledgeStore().bytes_from_object(knownledge_object)
                    #         try:
                    #             async with aiofiles.open("image.jpg", "wb") as f:
                    #                 await f.write(image)
                    #                 await message.channel.send(file=discord.File("image.jpg"))
                    #         except Exception as e:
                    #             logger.error(f"save image error:{e}")
                    #             logger.exception(e)
                    #         return
                    # else:
                    #     pos = resp_msg.body.find("audio file")
                    #     if pos != -1:
                    #         audio_file = resp_msg.body[pos+11:].strip()
                    #         if audio_file.startswith("\""):
                    #             audio_file = audio_file[1:-1]
                    #         await message.channel.send(file=discord.File(audio_file))
                    #         return
                    await message.channel.send(resp_msg.body)
                else:
                    if resp_msg.is_image_msg():
                        text, images = resp_msg.get_image_body()
                        files = []
                        for image in images:
                            files.append(discord.File(image))
                        await message.channel.send(content=text, files=files)
                    elif resp_msg.is_video_msg():
                        text, video_file = resp_msg.get_video_body()
                        await message.channel.send(text, file=discord.File(video_file))
                    elif resp_msg.is_audio_msg():
                        text, audio_file = resp_msg.get_audio_body()
                        await message.channel.send(text, file=discord.File(audio_file))
                    else:
                        await message.channel.send(resp_msg.body)

        asyncio.create_task(client.start(self.token))
        self.client = client
        print("start finish")

    async def close(self) -> None:
        await self.client.close()
        self.client = None

    async def _process_message(self, msg: AgentMsg) -> None:
        logger.warn(f"process message {msg.msg_id} from {msg.sender} to {msg.target}")
