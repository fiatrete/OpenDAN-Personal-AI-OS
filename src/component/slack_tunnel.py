import asyncio
import datetime
import json
import logging
import os.path
import re
import uuid
import time

import aiofiles
import aiohttp
from slack_bolt.adapter.socket_mode.websockets import AsyncSocketModeHandler
from slack_bolt.app.async_app import AsyncApp

from aios import KnowledgeStore, ObjectType
from aios.frame.tunnel import AgentTunnel
from aios.proto.agent_msg import AgentMsg, AgentMsgType
from aios.storage.storage import AIStorage

logger = logging.getLogger(__name__)


async def download_file(url: str, file_path: str, token: str) -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers={"Authorization": f"Bearer {token}"}) as resp:
            if resp.status == 200:
                f = await aiofiles.open(file_path, mode='wb')
                while True:
                    chunk = await resp.content.read(1024)
                    if not chunk:
                        break
                    await f.write(chunk)
                await f.close()


class SlackTunnel(AgentTunnel):
    type: str
    token: str
    app_token: str
    slack_cache: str
    app: AsyncSocketModeHandler

    def __init__(self):
        super().__init__()
        self.type = "SlackTunnel"
        self.token = ""
        self.slack_cache = os.path.join(AIStorage.get_instance().get_myai_dir(), "slack")
        if not os.path.exists(self.slack_cache):
            os.makedirs(self.slack_cache)

    @classmethod
    def register_to_loader(cls):
        async def load_slack_tunnel(config: dict) -> AgentTunnel:
            result_tunnel = SlackTunnel()
            if await result_tunnel.load_from_config(config):
                return result_tunnel
            else:
                return None

        AgentTunnel.register_loader("SlackTunnel", load_slack_tunnel)

    async def load_from_config(self, config: dict) -> bool:
        self.target_id = config["target"]
        self.tunnel_id = config["tunnel_id"]

        self.type = "SlackTunnel"
        self.token = config["token"]
        self.app_token = config["app_token"]

        return True

    def get_cache_path(self) -> str:
        today = datetime.datetime.today()
        path = os.path.join(self.slack_cache, str(today.year), str(today.month))
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def post_message(self, msg: AgentMsg) -> None:
        pass

    async def start(self) -> bool:
        app = AsyncApp(token=self.token)

        bot_info = await app.client.auth_test()

        @app.event("message")
        async def _handle_message(event):
            logger.info(json.dumps(event))
            ty = event["type"]
            if ty != "message":
                return

            user = event["user"]
            user_info = await app.client.users_info(user=user)

            if not user_info["ok"]:
                return

            user_info = user_info["user"]

            mime_type = None
            images = []
            file_type = None
            video_file = None
            audio_file = None


            if "files" in event:
                files = event["files"]
                if files is not None and len(files) > 0:
                    for file in files:
                        if file["mode"] == "tombstone":
                            continue

                        file_path = os.path.join(self.get_cache_path(), file["id"] + "." + file["filetype"])
                        file_info = await app.client.files_info(file=file["id"])
                        if not file_info["ok"]:
                            continue
                        await download_file(file_info["file"]["url_private_download"], file_path, self.token)

                        mime_type = file["mimetype"]
                        if file["mimetype"].startswith("image/"):
                            if file_type is None:
                                file_type = "image"
                            elif file_type != "image":
                                break
                            images.append(file_path)
                        elif file["mimetype"].startswith("video/"):
                            if file_type is None:
                                file_type = "video"
                            video_file = file_path
                            break
                        elif file["mimetype"].startswith("audio/"):
                            if file_type is None:
                                file_type = "audio"
                            audio_file = file_path
                            break

            agent_msg = AgentMsg()
            agent_msg.topic = "_slack"
            agent_msg.msg_id = "discord_msg#" + event["client_msg_id"] + "#" + uuid.uuid4().hex
            agent_msg.target = self.target_id
            agent_msg.create_time = time.time()
            agent_msg.sender = user_info["name"]
            self.ai_bus.register_message_handler(agent_msg.sender, self._process_message)

            content = re.sub("<@.+>", "", event["text"]).strip()

            blocks = event["blocks"]
            is_metion = False
            for block in blocks:
                if block["type"] == "rich_text":
                    elements = block["elements"]
                    for element in elements:
                        if element["type"] == "rich_text_section":
                            elements = element["elements"]

                            for element in elements:
                                if element["type"] == "user":
                                    if element["user_id"] == bot_info.get("user_id"):
                                        is_metion = True
                                        break

            if not is_metion:
                agent_msg.msg_type = AgentMsgType.TYPE_GROUPMSG

            if file_type is None:
                agent_msg.body = content
            elif file_type == "image":
                agent_msg.body = agent_msg.create_image_body(images, content)
                agent_msg.body_mime = mime_type
            elif file_type == "video":
                agent_msg.body = agent_msg.create_video_body(video_file, content)
                agent_msg.body_mime = mime_type
            elif file_type == "audio":
                agent_msg.body = agent_msg.create_audio_body(audio_file, content)
                agent_msg.body_mime = mime_type


            resp_msg: AgentMsg = await self.ai_bus.send_message(agent_msg)
            if resp_msg is None:
                await app.client.chat_postMessage(channel=event["channel"], text=f"System Error: Timeout,{self.target_id}  no resopnse! Please check logs/aios.log for more details!")
            else:
                if resp_msg.body_mime is None:
                    if resp_msg.body is None:
                        return

                    if len(resp_msg.body) < 1:
                        return

                    knownledge_object = KnowledgeStore().parse_object_in_message(resp_msg.body)
                    if knownledge_object is not None:
                        if knownledge_object.get_object_type() == ObjectType.Image:
                            image = KnowledgeStore().bytes_from_object(knownledge_object)
                            try:
                                async with aiofiles.open("image.jpg", "wb") as f:
                                    await f.write(image)
                                    await app.client.files_upload_v2(channel=event["channel"], file="image.jpg")
                            except Exception as e:
                                logger.error(f"save image error:{e}")
                                logger.exception(e)
                            return
                    else:
                        pos = resp_msg.body.find("audio file")
                        if pos != -1:
                            audio_file = resp_msg.body[pos+11:].strip()
                            if audio_file.startswith("\""):
                                audio_file = audio_file[1:-1]
                            await app.client.files_upload_v2(channel=event["channel"], file=audio_file)
                            return
                    await app.client.chat_postMessage(channel=event["channel"], text=resp_msg.body)
                else:
                    if resp_msg.is_image_msg():
                        text, images = resp_msg.get_image_body()
                        file_uploads = []
                        for image in images:
                            file_uploads.append({"file": image})
                        await app.client.files_upload_v2(channel=event["channel"], file_uploads=file_uploads, initial_comment=text)
                    elif resp_msg.is_video_msg():
                        text, video_file = resp_msg.get_video_body()
                        await app.client.files_upload_v2(channel=event["channel"], file=video_file, initial_comment=text)
                    elif resp_msg.is_audio_msg():
                        text, audio_file = resp_msg.get_audio_body()
                        await app.client.files_upload_v2(channel=event["channel"], file=audio_file, initial_comment=text)
                    else:
                        await app.client.chat_postMessage(channel=event["channel"], text=resp_msg.body)

        handle = AsyncSocketModeHandler(app, self.app_token)
        asyncio.create_task(handle.start_async())
        self.app = handle
        return True

    async def close(self) -> None:
        await self.app.close_async()
        self.app = None

    async def _process_message(self, msg: AgentMsg) -> None:
        logger.warn(f"process message {msg.msg_id} from {msg.sender} to {msg.target}")
