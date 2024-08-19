# aiso shell like bash for linux
import asyncio
import sys
import os
import logging
import re
import toml
import shlex
from logging.handlers import RotatingFileHandler

from typing import Any, Optional, TypeVar, Tuple, Sequence
import argparse

from prompt_toolkit import HTML, PromptSession, prompt,print_formatted_text
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.selection import SelectionState
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.styles import Style


directory = os.path.dirname(__file__)
sys.path.append(directory + '/../../')

# import os
# os.environ['HTTP_PROXY'] = '127.0.0.1:10809'
# os.environ['HTTPS_PROXY'] = '127.0.0.1:10809'

import proxy
from aios import *
import local_compute_node_builder
from component.llama_node.local_llama_compute_node import LocalLlama_ComputeNode

sys.path.append(directory + '/../../component/')

from google_node import *
from llama_node import *
from openai_node import *
from sd_node import *

from agent_manager import AgentManager
from workflow_manager import WorkflowManager
#from knowledge_manager import KnowledgePipelineManager
from tg_tunnel import TelegramTunnel
from email_tunnel import EmailTunnel
from discord_tunnel import DiscordTunnel
from slack_tunnel import SlackTunnel
from common_environment import FilesystemEnvironment, ShellEnvironment
#from common_environment import ScanLocalDocument, ParseLocalDocument

from compute_node_config import *


logger = logging.getLogger(__name__)

shell_style = Style.from_dict({
    'title': '#87d7ff bold', #RGB
    'content': '#007f00', # resp content
    'prompt': '#00FF00',
    'error': '#8F0000 bold'
})

class AIOS_Shell:
    def __init__(self,username:str) -> None:
        self.username = username
        self.current_target = "_"
        self.current_topic = "default"
        self.is_working = True

    def declare_all_user_config(self):
        user_data_dir = AIStorage.get_instance().get_myai_dir()
        contact_config_path =os.path.abspath(f"{user_data_dir}/contacts.toml")
        cm = ContactManager.get_instance(contact_config_path)
        cm.load_data()

        user_config = AIStorage.get_instance().get_user_config()
        user_config.add_user_config("username","username is your full name when using AIOS",False,None)
        user_config.add_user_config("user_telegram","Your telgram username",False,None)
        user_config.add_user_config("user_email","Your email",False,None)
        user_config.add_user_config("user_notes","Introduce yourself to your Agent!",False,None)

        user_config.add_user_config("feature.llama","enable Local-llama feature",True,"False")
        user_config.add_user_config("feature.aigc","enable AIGC feature",True,"False")

        openai_node = OpenAI_ComputeNode.get_instance()
        openai_node.declare_user_config()

        user_config.add_user_config("shell.current","last opened target and topic",True,"default@Jarvis")
        proxy.declare_user_config()

        # google_text_to_speech = GoogleTextToSpeechNode.get_instance()
        # google_text_to_speech.declare_user_config()

        Local_Stability_ComputeNode.declare_user_config()

        #Stability_ComputeNode.declare_user_config()

    def init_global_action_lib(self):
        AgentMemory.register_actions()


    async def _handle_no_target_msg(self,bus:AIBus,target_id:str) -> bool:
        agent : AIAgent = await AgentManager.get_instance().get(target_id)
        if agent is not None:
            bus.register_message_handler(target_id,agent._process_msg)
            return True

        a_workflow = await WorkflowManager.get_instance().get_workflow(target_id)
        if a_workflow is not None:
            bus.register_message_handler(target_id,a_workflow._process_msg)
            return True

        a_contact = ContactManager.get_instance().find_contact_by_name(target_id)
        if a_contact is not None:
            bus.register_message_handler(target_id,a_contact._process_msg)
            return True

        return False

    async def is_agent(self,target_id:str) -> bool:
        agent : AIAgent = await AgentManager.get_instance().get(target_id)
        if agent is not None:
            return True
        else:
            return False

    async def initial(self) -> bool:
        cm = ContactManager.get_instance()
        owner = cm.find_contact_by_name(self.username)
        if owner is None:
            owner = Contact(self.username)
            owner.added_by = self.username
            owner.relationship = "Principal"
            owner.email = AIStorage.get_instance().get_user_config().get_value("user_email")
            owner.telegram = AIStorage.get_instance().get_user_config().get_value("user_telegram")
            owner.notes = AIStorage.get_instance().get_user_config().get_value("user_notes")

            cm.add_contact(self.username,owner)

        # cal_env = CalenderEnvironment("calender")
        # await cal_env.start()
        # Environment.set_env_by_id("calender",cal_env)

        # workspace_env = ShellEnvironment("bash")
        # Environment.set_env_by_id("bash",workspace_env)

        # paint_env = PaintEnvironment("paint")
        # Environment.set_env_by_id("paint",paint_env)

        #AgentManager.get_instance().register_environment("bash", ShellEnvironment)
        #AgentManager.get_instance().register_environment("fs", FilesystemEnvironment)
        #AgentManager.get_instance().register_environment("knowledge", LocalKnowledgeBase)
        AgentWorkspace.register_ai_functions()
        AgentMemory.register_ai_functions()
        BaseKnowledgeGraph.register_ai_functions()
        ShellEnvironment.register_ai_functions()
       

        if await AgentManager.get_instance().initial() is not True:
            logger.error("agent manager initial failed!")
            return False
        if await WorkflowManager.get_instance().initial() is not True:
             logger.error("workflow manager initial failed!")
             return False

        open_ai_node = OpenAI_ComputeNode.get_instance()
        if await open_ai_node.initial() is not True:
            logger.error("openai node initial failed!")
            return False
        ComputeKernel.get_instance().add_compute_node(open_ai_node)

        whisper_node = WhisperComputeNode.get_instance()
        ComputeKernel.get_instance().add_compute_node(whisper_node);

        openai_tts_node = OpenAITTSComputeNode.get_instance()
        ComputeKernel.get_instance().add_compute_node(openai_tts_node)

        dall_e_node = DallEComputeNode.get_instance()
        if await dall_e_node.initial() is not True:
            logger.error("dall-e node initial failed!")
        else:
            await dall_e_node.start()
            ComputeKernel.get_instance().add_compute_node(dall_e_node)

        llama_nodes = ComputeNodeConfig.get_instance().initial()
        for llama_node in llama_nodes:
            llama_node.start()
            ComputeKernel.get_instance().add_compute_node(llama_node)

        if await AIStorage.get_instance().is_feature_enable("llama"):
            llama_ai_node = LocalLlama_ComputeNode()
            if await llama_ai_node.initial() is True:
                await llama_ai_node.start()
                ComputeKernel.get_instance().add_compute_node(llama_ai_node)
            else:
                logger.error("llama node initial failed!")
                await AIStorage.get_instance().set_feature_init_result("llama",False)


        # if await AIStorage.get_instance().is_feature_enable("aigc"):
            # try:
            #     google_text_to_speech_node = GoogleTextToSpeechNode.get_instance()
            #     google_text_to_speech_node.init()
            #     ComputeKernel.get_instance().add_compute_node(google_text_to_speech_node)
            # except Exception as e:
            #     logger.error(f"google text to speech node initial failed! {e}")
            #     await AIStorage.get_instance.set_feature_init_result("aigc",False)

            # stability_api_node = Stability_ComputeNode()
            # if await stability_api_node.initial() is not True:
            #     logger.error("stability api node initial failed!")
            # ComputeKernel.get_instance().add_compute_node(stability_api_node)



        # local_st_text_compute_node = LocalSentenceTransformer_Text_ComputeNode()
        # if local_st_text_compute_node.initial() is not True:
        #     logger.error("local sentence transformer text embedding node initial failed!")
        # else:
        #     ComputeKernel.get_instance().add_compute_node(local_st_text_compute_node)

        # local_st_image_compute_node = LocalSentenceTransformer_Image_ComputeNode()
        # if local_st_image_compute_node.initial() is not True:
        #     logger.error("local sentence transformer image embedding node initial failed!")
        # else:
        #     ComputeKernel.get_instance().add_compute_node(local_st_image_compute_node)


        await ComputeKernel.get_instance().start()

        AIBus().get_default_bus().register_unhandle_message_handler(self._handle_no_target_msg)
        #AIBus().get_default_bus().register_message_handler(self.username,self._user_process_msg)


        #pipelines = KnowledgePipelineManager.initial(os.path.join(AIStorage().get_instance().get_myai_dir(), "knowledge/pipelines"))
        #pipelines.register_input("scan_local", ScanLocalDocument)
        #pipelines.register_parser("parse_local", ParseLocalDocument)
        #pipelines.load_dir(os.path.join(AIStorage().get_instance().get_system_app_dir(), "knowledge_pipelines"))
        #pipelines.load_dir(os.path.join(AIStorage().get_instance().get_myai_dir(), "knowledge_pipelines"))
        #asyncio.create_task(pipelines.run())

        TelegramTunnel.register_to_loader()
        EmailTunnel.register_to_loader()
        DiscordTunnel.register_to_loader()
        SlackTunnel.register_to_loader()
        user_data_dir = str(AIStorage.get_instance().get_myai_dir())
        tunnels_config_path = os.path.abspath(f"{user_data_dir}/etc/tunnels.cfg.toml")
        tunnel_config = None
        try:
            tunnel_config = toml.load(tunnels_config_path)
            if tunnel_config is not None:
                await AgentTunnel.load_all_tunnels_from_config(tunnel_config)
        except Exception as e:
            logger.warning(f"load tunnels config from {tunnels_config_path} failed! {e}")


        return True


    def get_version(self) -> str:
        return "0.5.2"

    async def send_msg(self,msg:str,target_id:str,topic:str,sender:str = None, msg_mime:str=None) -> str:
        if sender == self.username:
            AIBus().get_default_bus().register_message_handler(self.username,self._user_process_msg)

        agent_msg = AgentMsg()
        agent_msg.set(sender,target_id,msg,body_mime=msg_mime)
        agent_msg.topic = topic
        resp = await AIBus.get_default_bus().send_message(agent_msg)
        if resp is not None:
            if resp.msg_type != AgentMsgType.TYPE_SYSTEM:
                return resp.body
            else:
                return f"Process Message Error: {resp.body} Please check logs/aios.log for more details!"
        else:
            return "System Error: Timeout, no resopnse! Please check logs/aios.log for more details!"

    async def _user_process_msg(self,msg:AgentMsg) -> AgentMsg:
        pass


    async def get_tunnel_config_from_input(self,tunnel_target,tunnel_type):
        tunnel_config = {}
        tunnel_config["tunnel_id"] = f"{tunnel_type}_2_{tunnel_target}"
        tunnel_config["target"] = tunnel_target
        input_table = {}
        tunnel_introduce : str = ""
        match tunnel_type:
            case "telegram":
                tunnel_config["type"] = "TelegramTunnel"
                input_table["token"] = UserConfigItem("telegram bot token\n You can get it from https://t.me/BotFather ,read https://core.telegram.org/bots#how-do-i-create-a-bot for more details")
                input_table["allow"] = UserConfigItem("allow group (default is member,you can choose contact or guest)")
            case "email":
                tunnel_config["type"] = "EmailTunnel"
                input_table["email"] = UserConfigItem("email address agent will use \n")
                input_table["imap"] = UserConfigItem("imap server address,like hostname:port")
                input_table["smtp"] = UserConfigItem("smtp server address,like hostname:port")
                input_table["user"] = UserConfigItem("mail server login user name")
                input_table["password"] = UserConfigItem("main server login password")
            case "discord":
                tunnel_config["type"] = "DiscordTunnel"
                input_table["token"] = UserConfigItem("discord bot token\n You can get it from https://discord.com/developers/applications ,read https://discordpy.readthedocs.io/en/stable/discord.html for more details")
            case "slack":
                tunnel_config["type"] = "SlackTunnel"
                input_table["token"] = UserConfigItem("slack bot token\n You can get it from https://api.slack.com/apps")
                input_table["app_token"] = UserConfigItem("slack app token\n You can get it from https://api.slack.com/apps")
            case _:
                error_text = FormattedText([("class:error", f"tunnel type {tunnel_type}not support!")])
                print_formatted_text(error_text,style=shell_style)
                return None

        intro_text = FormattedText([("class:prompt", tunnel_introduce)])
        print_formatted_text(intro_text,style=shell_style)
        for key,item in input_table.items():
            user_input = await try_get_input(f"{key} : {item.desc}")
            if user_input is None:
                return None

            tunnel_config[key] = user_input

        return tunnel_config

    async def append_tunnel_config(self,tunnel_config):
        user_data_dir = AIStorage.get_instance().get_myai_dir()
        tunnels_config_path = os.path.abspath(f"{user_data_dir}/etc/tunnels.cfg.toml")
        all_tunnels = None
        try:
            all_tunnels = toml.load(tunnels_config_path)
        except Exception as e:
            logger.warning(f"load tunnels config for append from {tunnels_config_path} failed! {e}")

        if all_tunnels is None:
            all_tunnels = {}

        all_tunnels[tunnel_config["tunnel_id"]] = tunnel_config
        try:
            f = open(tunnels_config_path,"w")
            if f:
                toml.dump(all_tunnels,f)
                logger.info(f"append tunnel config to {tunnels_config_path} success!")
            else:
                logger.warning(f"append tunnel config to {tunnels_config_path} failed!")
        except Exception as e:
            logger.warning(f"append tunnels config  from {tunnels_config_path} failed! {e}")

    async def handle_contact_commands(self,args):
        cm = ContactManager.get_instance()
        if len(args) < 1:
            return FormattedText([("class:error", f'/contact $contact_name,  Like /contact "Jim Green"')])
        contact_name = args[0]
        contact = cm.find_contact_by_name(contact_name)
        is_update = False
        if contact is not None:
            #show old info and ask user to update or remove
            is_update = True
            op_str = await try_get_input(f"Contact {contact_name} already exist, update or remove? (u/r)")
            if op_str is None:
                return None
            if op_str == "r":
                cm.remove_contact(contact_name)
                return FormattedText([("class:title", f"remove {contact_name} success!")])
            else:
                print(f"old info: {contact}")
        else:
            contact = Contact(contact_name)

        contact.is_family_member = False
        is_family_member = await try_get_input(f"Is {contact_name} your family member? (y/n)")
        if is_family_member is not None:
            if is_family_member == "y" or is_family_member == "Y":
                contact.is_family_member = True
        else:
            return None

        contact_telegram = await try_get_input(f"Input {contact_name}'s telegram username:")
        if contact_telegram is None:
            return None
        contact.telegram = contact_telegram

        contact_email = await try_get_input(f"Input {contact_name}'s email:")
        if contact_email is None:
            return None
        contact.email = contact_email

        contact_phone = await try_get_input(f"Input {contact_name}'s phone (optional):")
        if contact_phone is not None:
            contact.phone = contact_phone

        contact_note = await try_get_input(f"Input {contact_name}'s note (optional):")
        if contact_note is not None:
            contact.notes = contact_note

        contact.added_by = self.username
        if is_update:
            cm.set_contact(contact_name,contact)
        else:
            cm.add_contact(contact_name,contact)

    async def handle_knowledge_commands(self, args):
        show_text = FormattedText([("class:title", "sub command not support!\n"
                              "/knowledge pipelines\n" 
                              "/knowledge journal $pipeline [$topn]\n"
                              "/knowledge query $object_id\n")])
        if len(args) < 1:
            return show_text
        sub_cmd = args[0]
        if sub_cmd == "pipelines":
            pipelines = KnowledgePipelineManager.get_instance().get_pipelines()
            print_formatted_text("\r\n".join(pipeline.get_name() for pipeline in pipelines))
        if sub_cmd == "journal":
            try:
                name = args[1]
                topn = 10 if len(args) == 2 else int(args[2])
                journals = [str(journal) for journal in KnowledgePipelineManager.get_instance().get_pipeline(name).get_journal().latest_journals(topn)]
                print_formatted_text("\r\n".join(str(journal) for journal in journals))
            except ValueError:
                return FormattedText([("class:title", f"/knowledge journal failed: {args[1]} is not a valid integer.\n")])
        if sub_cmd == "query":
            if len(args) < 2:
                return show_text
            from knowledge import ObjectID, ObjectType
            object_id = ObjectID.from_base58(args[1])
            if object_id.get_object_type() == ObjectType.Image:
                from PIL import Image
                import io
                image = KnowledgeStore().load_object(object_id)
                image_data = KnowledgeStore().bytes_from_object(image)
                image = Image.open(io.BytesIO(image_data))
                image.show()

    async def handle_node_commands(self, args):
        show_text = FormattedText([("class:title", "sub command not support!\n" 
                              "/node add $model_name $url\n"
                              "/node create\n"
                              "/node rm $model_name $url\n"
                              "/node list\n")])
        if len(args) < 1:
            return show_text
        sub_cmd = args[0]
        if sub_cmd == "create":
            await local_compute_node_builder.build(session, shell_style)
        elif sub_cmd == "add":
            if len(args) < 3:
                return show_text

            model_name = args[1]
            url = args[2]
            ComputeNodeConfig.get_instance().add_node("llama", url, model_name)
            ComputeNodeConfig.get_instance().save()
            node = LocalLlama_ComputeNode(url, model_name)
            node.start()
            ComputeKernel.get_instance().add_compute_node(node)
        elif sub_cmd == "rm":
            if len(args) < 3:
                return show_text

            model_name = args[1]
            url = args[2]
            ComputeNodeConfig.get_instance().remove_node("llama", url, model_name)
            ComputeNodeConfig.get_instance().save()
        elif sub_cmd == "list":
            print_formatted_text(ComputeNodeConfig.get_instance().list())

    async def call_func(self,func_name, args):
        match func_name:
            case 'send':
                show_text = FormattedText([("class:error", f'send args error,/send Tracy "Hello! It is a good day!" default')])
                sender = None
                if len(args) == 3:
                    target_id = args[0]
                    msg_content = args[1]
                    topic = args[2]
                    sender = self.username
                elif len(args) == 4:
                    target_id = args[0]
                    msg_content = args[1]
                    topic = args[2]
                    sender = args[3]

                resp = await self.send_msg(msg_content,target_id,topic,sender)
                show_text = FormattedText([("class:title", f"{self.current_topic}@{self.current_target} >>> "),
                                        ("class:content", resp)])
                return show_text
            case 'send_img':
                sender = None
                if len(args) == 4:
                    target_id = args[0]
                    msg_content = args[1]
                    image_path = args[2]
                    topic = args[3]
                    sender = self.username
                elif len(args) == 5:
                    target_id = args[0]
                    msg_content = args[1]
                    image_path = args[2]
                    topic = args[3]
                    sender = args[4]

                ext = os.path.splitext(image_path)[1][1:]
                resp = await self.send_msg(AgentMsg.create_image_body([image_path], msg_content),
                                           target_id,
                                           topic,
                                           sender,
                                           f"image/{ext}")
                show_text = FormattedText([("class:title", f"{self.current_topic}@{self.current_target} >>> "),
                                           ("class:content", resp)])
                return show_text
            case 'send_video':
                sender = None
                if len(args) == 4:
                    target_id = args[0]
                    msg_content = args[1]
                    video_path = args[2]
                    topic = args[3]
                    sender = self.username
                elif len(args) == 5:
                    target_id = args[0]
                    msg_content = args[1]
                    video_path = args[2]
                    topic = args[3]
                    sender = args[4]

                ext = os.path.splitext(video_path)[1][1:]
                resp = await self.send_msg(AgentMsg.create_video_body(video_path, msg_content),
                                           target_id,
                                           topic,
                                           sender,
                                           f"video/{ext}")
                show_text = FormattedText([("class:title", f"{self.current_topic}@{self.current_target} >>> "),
                                           ("class:content", resp)])
                return show_text
            case 'set_config':
                show_text = FormattedText([("class:error", f"set config args error,/set_config $config_item! ")])
                if len(args) == 1:
                    key = args[0]
                    config_item = AIStorage.get_instance().get_user_config().get_config_item(key)
                    old_value = AIStorage.get_instance().get_user_config().get_value(key)

                    if config_item is not None:
                        value = await session.prompt_async(f"{key} : {config_item.desc} \nCurrent : {old_value}\nPlease input new value:",style=shell_style)
                        AIStorage.get_instance().get_user_config().set_value(key,value)
                        await AIStorage.get_instance().get_user_config().save_to_user_config()
                        show_text = FormattedText([("class:title", f"set {key} to {value} success!")])
                    else:
                        show_text = FormattedText([("class:error", f"set config failed! config item {key} not found!")])

                return show_text
            case 'connect':
                show_text = FormattedText([("class:error", "args error, /connect $target")])
                if len(args) < 1:
                    return show_text
                tunnel_target = args[0]
                if len(args) < 2:
                    tunnel_type = "telegram"
                else:
                    tunnel_type = args[1]
                tunnel_type = tunnel_type.lower()
                tunnel_config = await self.get_tunnel_config_from_input(tunnel_target,tunnel_type)
                if tunnel_config:
                    if await AgentTunnel.load_tunnel_from_config(tunnel_config):
                        # append
                        await self.append_tunnel_config(tunnel_config)
                        show_text = FormattedText([("class:title", f"connect to {tunnel_target} success!")])

                return show_text
            case 'knowledge':
                return await self.handle_knowledge_commands(args)
            case 'contact':
                return await self.handle_contact_commands(args)
            case 'think':
                if len(args) >= 1:
                    target_id = args[0]
                    the_agent = await AgentManager.get_instance().get(target_id)
                    if the_agent is not None:
                        await the_agent._do_think()
            case 'wakeup':
                if len(args) >= 1:
                    target_id = args[0]
                    the_agent = await AgentManager.get_instance().get(target_id)
                    if the_agent is not None:
                        the_agent.wake_up()
            case 'open':
                if len(args) >= 1:
                    target_id = args[0]
                else:
                    show_text = FormattedText([("class:error", "/open Need Target Agent/Workflow ID! like /open Jarvis default")])
                    return show_text

                if len(args) >= 2:
                    topic = args[1]
                else:
                    topic = "default"

                target_exist = False
                if await AgentManager.get_instance().is_exist(target_id):
                    target_exist = True
                # if await WorkflowManager.get_instance().is_exist(target_id):
                #     target_exist = True

                if target_exist is False:
                    show_text = FormattedText([("class:error", f"Target {target_id} not exist!")])
                    return show_text

                self.current_target = target_id
                self.current_topic = topic
                show_text = FormattedText([("class:title", f"current session switch to {topic}@{target_id}")])
                AIStorage.get_instance().get_user_config().set_value("shell.current",f"{self.current_topic}@{self.current_target}")
                await AIStorage.get_instance().get_user_config().save_to_user_config()
                return show_text
            case 'enable':
                if len(args) >= 1:
                    feature = args[0]
                else:
                    show_text = FormattedText([("class:error", "/enable Need Feature Name! like /enable llama")])
                    return show_text

                if await AIStorage.get_instance().is_feature_enable(feature):
                    show_text = FormattedText([("class:title", f"Feature {feature} already enabled!")])
                    return show_text

                await AIStorage.get_instance().enable_feature(feature)
                show_text = FormattedText([("class:title", f"Feature {feature} enabled!")])
                return show_text
            case 'disable':
                if len(args) >= 1:
                    feature = args[0]
                else:
                    show_text = FormattedText([("class:error", "/disable Need Feature Name! like /disable llama")])
                    return show_text

                if not await AIStorage.get_instance().is_feature_enable(feature):
                    show_text = FormattedText([("class:title", f"Feature {feature} already disabled!")])
                    return show_text

                await AIStorage.get_instance().disable_feature(feature)
                show_text = FormattedText([("class:title", f"Feature {feature} disabled!")])
                return show_text
            #case 'login':
            #    if len(args) >= 1:
            #        self.username = args[0]
            #    AIBus().get_default_bus().register_message_handler(self.username,self._user_process_msg)

            #    return self.username + " login success!"
            case 'history':
                num = 10
                offset = 0
                if args is not None:
                    if len(args) >= 1:
                        num = args[0]
                    if len(args) >= 2:
                        offset = args[1]

                db_path = ""
                if await self.is_agent(self.current_target):
                    db_path = AgentManager.get_instance().db_path
                # else:
                #     db_path = WorkflowManager.get_instance().db_file
                chatsession:AIChatSession = AIChatSession.get_session(self.current_target,f"{self.username}#{self.current_topic}",db_path,False)
                if chatsession is not None:
                    msgs = chatsession.read_history(num,offset)
                    format_texts = []
                    for msg in msgs:
                        format_texts.append(("class:content",f"{msg.sender} >>> {msg.body}"))
                        format_texts.append(("",f"\n-------------------\n"))
                    return FormattedText(format_texts)
                return FormattedText([("class:title", f"chatsession not found")])
            case 'node':
                return await self.handle_node_commands(args)
            case 'exit':
                os._exit(0)
            case 'help':
                return FormattedText([("class:title", f"GO to https://github.com/fiatrete/OpenDAN-Personal-AI-OS/issues ^_^")])


##########################################################################################################################
history = FileHistory('aios_shell_history.txt')
session = PromptSession(history=history)

def parse_function_call(func_string):
    if len(func_string) > 2:
        if func_string[0] == '/' and func_string[1] != '/':
            str_list = shlex.split(func_string[1:])
            func_name = str_list[0]
            params = str_list[1:]
            return func_name, params
    else:
        return None

async def try_get_input(desc:str,mutil_line:bool = False,check_func:callable = None) -> str:
    user_input = await session.prompt_async(f"{desc} \nType /exit to abort. \nPlease input:",style=shell_style)
    err_str = ""
    if check_func is None:
        if len(user_input) > 0:
            if user_input != "/exit":
                if mutil_line is False:
                    user_input = user_input.strip()
                return user_input
            else:
                return None

    else:
        is_ok,err_str = check_func(user_input)
        if is_ok:
            return user_input

    error_text = FormattedText([("class:error", err_str)])
    print_formatted_text(error_text,style=shell_style)
    return await try_get_input(desc,check_func)

async def get_user_config_from_input(check_result:dict) -> bool:
    for key,item in check_result.items():
        user_input = await try_get_input(f"System config {key} ({item.desc}) not define!")
        if user_input is None:
            if item.is_optional:
                continue
            else:
                True
        if user_input:
            if len(user_input) > 0:
                AIStorage.get_instance().get_user_config().set_value(key,user_input)

    await AIStorage.get_instance().get_user_config().save_to_user_config()
    return True

async def main_daemon_loop(shell:AIOS_Shell):
    while shell.is_working:
        await asyncio.sleep(1)

    return 0

def print_welcome_screen():
    print("\033[1;31m")
    logo = """
\t   _______                    ____________________   __
\t   __  __ \______________________  __ \__    |__  | / /
\t   _  / / /__  __ \  _ \_  __ \_  / / /_  /| |_   |/ / 
\t   / /_/ /__  /_/ /  __/  / / /  /_/ /_  ___ |  /|  /  
\t   \____/ _  .___/\___//_/ /_//_____/ /_/  |_/_/ |_/   
\t           /_/                                          

    """
    print(logo)
    print("\033[0m")

    print("\033[1;32m \t\tWelcome to OpenDAN - Your Personal AI OS\033[0m\n")

    introduce = """
\tOpenDAN (Open and Do Anything Now with AI) is revolutionizing the 
\tAI landscape with its Personal AI Operating System. Designed for 
\tseamless integration of diverse AI modules, it ensures unmatched 
\tinteroperability. OpenDAN empowers users to craft powerful AI agents:
\tfrom butlers and assistants to personal tutors and digital companions.
\tAll while retaining control. These agents can team up to tackle complex  
\tchallenges, integrate with existing services, and command IoT devices. 
\t
\tWith OpenDAN, we're putting AI in your hands, making life simpler and smarter.
\t
\t================ AIOS Shell Handbook ================

\033[1;94m\tUnderstand the Shell Prompt :\033[0m [current_username]<->[current_topic]@[current_target]$ 
\033[1;94m\tTalk with Agent/Workflow :\033[0m Directly input and wait.
\033[1;94m\tTalk with another Agent/Workflow :\033[0m /open $target_name [$topic_name]
\033[1;94m\tInstall new Agent/Workflow :\033[0m /install $agent_name (Not support at 0.5.1)
\t\t(For Developer) Download and unzip Agent to ~/myai/agents or ~/myai/workflows
\033[1;94m\tView chat History :\033[0m /history
\033[1;94m\tChange AIOS Owner's telegram username :\033[0m /set_config telegram
\033[1;94m\tChange OpenAI API Token :\033[0m /set_config $openai_api_key
\033[1;94m\tGive your Agent a Telegram account :\033[0m /connect $agent_name
\033[1;94m\tAdd personal files to the AI Knowledge Base. \033[0m
\t\t1) Copy your file to ~/myai/data 
\033[1;94m\tSearch your knowledge base :\033[0m /open Mia
\033[1;94m\tCheck the progress of AI reading personal data :\033[0m /knowledge $pipeline journal
\033[1;94m\tQuery object with ID in knowledge base :\033[0m /knowledge query $object_id
\033[1;94m\tOpen AI Bash (For Developer Only):\033[0m /open ai_bash
\033[1;94m\tEnable AIGC Feature :\033[0m /enable aigc
\033[1;94m\tEnable llama (Local LLM Kernel) :\033[0m /enable llama
"""
    print(introduce)

    print(f"\033[1;34m \t\tVersion: {AIOS_Version}\n\033")
    print("\033[1;33m \tOpenDAN is an open-source project, let's define the future of Humans and AI together.\033[0m")
    print("\033[1;33m \tGithub\t: https://github.com/fiatrete/OpenDAN-Personal-AI-OS\033[0m")
    print("\033[1;33m \tWebsite\t: https://www.opendan.ai\033[0m")
    print("\n\n")


async def main():
    print_welcome_screen()
    print("Booting...")

    if os.path.isdir(f"{directory}/../../../rootfs"):
        AIStorage.get_instance().is_dev_mode = True
    else:
        AIStorage.get_instance().is_dev_mode = False


    if AIStorage.get_instance().is_dev_mode:
        logging.basicConfig(filename="aios_shell.log",filemode="w",encoding='utf-8',force=True,
                            level=logging.INFO,
                            format='[%(asctime)s]%(name)s[%(levelname)s]: %(message)s')
    else:
        dir_path = f"{AIStorage.get_instance().get_myai_dir()}/logs"
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        log_file = f"{AIStorage.get_instance().get_myai_dir()}/logs/aios.log"
        handler = RotatingFileHandler(log_file, maxBytes=50*1024*1024, backupCount=100)

        logging.basicConfig(handlers=[handler],
                            level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    is_daemon = False
    logger.info(f"Check Host OS :{os.name}")
    if os.name != 'nt':
        is_daemon = os.fstat(0) != os.fstat(1) or os.fstat(0) != os.fstat(2)

    shell = AIOS_Shell("user")
    shell.declare_all_user_config()
    await AIStorage.get_instance().initial()
    check_result = AIStorage.get_instance().get_user_config().check_config()
    if check_result is not None:
        if is_daemon:
            logger.error(check_result)
            return 1
        else:
            #Remind users to enter necessary configurations.
            if await get_user_config_from_input(check_result) is False:
                return 1
    shell.username = AIStorage.get_instance().get_user_config().get_value("username")
    init_result = await shell.initial()
    proxy.apply_storage()

    if init_result is False:
        if is_daemon:
            logger.error("aios shell initial failed!")
            return 1
        else:
            print("aios shell initial failed!")
            return 1

    print(f"aios shell {shell.get_version()} ready. Daemon:{is_daemon}")
    logger.info(f"aios shell {shell.get_version()} ready. Daemon:{is_daemon}")
    if is_daemon:
        return await main_daemon_loop(shell)

    completer = WordCompleter(['/send $target $msg $topic',
                               '/send_img $target $msg $img_path $topic',
                               '/send_video $target &msg &video_path $topic',
                               '/open $target $topic',
                               '/history $num $offset',
                               '/connect $target',
                               '/contact $name',
                               '/knowledge pipelines',
                               '/knowledge journal $pipeline [$topn]',
                               '/knowledge query $object_id',
                               '/set_config $key',
                               '/enable $feature',
                               '/disable $feature',
                               '/node add $model_name $url',
                               '/node create',
                               '/node rm $model_name $url',
                               '/node list',
                               '/show',
                               '/exit',
                               '/help'], ignore_case=True)

    current = AIStorage.get_instance().get_user_config().get_value("shell.current")
    current = current.split("@")
    shell.current_target = current[1]
    shell.current_topic = current[0]

    await asyncio.sleep(0.2)
    while True:
        user_input = await session.prompt_async(f"{shell.username}<->{shell.current_topic}@{shell.current_target}$ ",completer=completer,style=shell_style)
        if len(user_input) <= 1:
            continue

        func_call = parse_function_call(user_input)
        show_text = None
        if func_call:
            show_text = await shell.call_func(func_call[0], func_call[1])
        else:
            resp = await shell.send_msg(user_input,shell.current_target,shell.current_topic,shell.username)
            show_text = FormattedText([
                ("class:title", f"{shell.current_topic}@{shell.current_target} >>> "),
                ("class:content", resp)
            ])

        print_formatted_text(show_text,style=shell_style)
        #print_formatted_text(f"{shell.username}<->{shell.current_topic}@{shell.current_target} >>> {resp}",style=shell_style)


if __name__ == "__main__":
    asyncio.run(main())

