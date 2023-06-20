import asyncio
import os
from asyncio import Queue, Task
import socketio
from jarvis import CFG
from jarvis.ai_agent import agent_factory
from jarvis.ai_agent.base_agent import BaseAgent
from jarvis.functional_modules.caller_context import CallerContext
from jarvis.logger import logger
from jarvis.utils import function_error
from jarvis.utils.incoming_chat_message_parser import assemble_json_message, IncomingChatMessage


class SioConnection:
    async def emit(self, msg_type: str, msg: str, user_id: str, session_id: str, message_id: str):
        """
        msg_type: 'text', 'markdown', 'notification', 'image', 'end'
        """
        raise Exception("Not implemented!")

    async def safe_emit(self, msg_type: str, msg: str, user_id: str, session_id: str, msg_id: str):
        try:
            await self.emit(msg_type, msg, user_id, session_id, msg_id)
        except:
            logger.debug("Failed to safe emit text")
            pass


class SioServerConnection(SioConnection):
    _sio: socketio.AsyncServer = None
    _sid: str = None

    def __init__(self, sio: socketio.AsyncServer, sid):
        self._sio = sio
        self._sid = sid

    async def emit(self, msg_type: str, msg: str, user_id: str, session_id: str, message_id: str):
        data = assemble_json_message(msg_type, msg, user_id, session_id, message_id)
        await self._sio.emit('chat_message', data, self._sid)


class SioClientConnection(SioConnection):
    _sio: socketio.AsyncClient = None

    def __init__(self, sio: socketio.AsyncClient):
        self._sio = sio

    async def emit(self, msg_type: str, msg: str, user_id: str, session_id: str, message_id: str):
        data = assemble_json_message(msg_type, msg, user_id, session_id, message_id)
        await self._sio.emit('chat_message', data)


def _get_history_file_dir():
    if CFG.chat_history_dir is None:
        return None
    if CFG.use_private_ai:
        sub_path = "private"
    else:
        sub_path = "gpt"
    return os.path.join(CFG.chat_history_dir, sub_path)


class Session(CallerContext):
    _agent: BaseAgent = None
    _sio: SioConnection = None
    _session_id: str = None
    _tz_offset: int = 0  # timezone offset, in hours. = local_time - UTC0
    _last_image: str = None

    _history_dir: str = None

    _message_handle_coro: Task = None
    _message_queue: Queue = None
    _is_running: bool = True

    _last_message_id: str = None  # keep last message's ID to avoid handling duplicated messages

    # Tese variables start and end with '_' is temporary, valid only during handling messages
    _message_user_id_: str = None
    _message_id_: str = None

    def __init__(self, sio: SioConnection, session_id: str):
        agent = agent_factory.create_agent(self)
        super().__init__(agent)
        self._agent = agent
        self._sio = sio
        self._session_id = session_id
        self._message_queue = Queue()

        self._history_dir = _get_history_file_dir()

        self._is_running = True
        self._message_handle_coro = asyncio.ensure_future(self._handle_messages())
        self._load_history()

    def __del__(self):
        self._save_history()

    async def stop(self):
        self._is_running = False
        self._message_queue.put_nowait(None)
        await self._message_handle_coro

    def set_sio(self, sio: SioConnection):
        self._sio = sio

    async def _handle_messages(self):
        try:
            while self._is_running:
                msg = await self._message_queue.get()
                if msg is None:
                    break
                logger.debug(f"Got one message from {msg.message_content}, id{msg.message_id}")
                self._message_user_id_ = msg.user_id
                self._message_id_ = msg.message_id
                try:
                    await self._agent.feed_prompt(msg.message_content)
                except (InterruptedError, asyncio.CancelledError) as e:
                    logger.info("_handle_messages coroutine interrupted, exit")
                    break
                except BaseException as e:
                    if isinstance(e, function_error.FunctionError) and e.code == function_error.EC_RESET:
                        assert self._message_id_ is None
                    else:
                        if self._message_id_ is not None:
                            logger.error(f"Failed to handle request: {str(e)}")
                            await self._safe_reply_text('Sorry, failed to response your previous request')
                finally:
                    if self._message_id_ is not None:
                        await self._sio.safe_emit('end', '', self._message_user_id_, self._session_id,
                                                  self._message_id_)
                self._save_history()

            logger.debug(f"Coro exit: {self._session_id}")
        except BaseException as e:
            if isinstance(e, InterruptedError) or isinstance(e, asyncio.CancelledError):
                return
            logger.error(f"An unhandled error {str(e)}")

    async def on_chat_message(self, msg: IncomingChatMessage):
        if self._last_message_id == msg.message_id:
            logger.warn(f'Duplicated message id, discard: {msg.message_id}')
            return
        else:
            self._last_message_id = msg.message_id
        self._message_queue.put_nowait(msg)

    async def _safe_reply_text(self, msg: str):
        try:
            await self.reply_text(msg)
        except:
            logger.debug("Failed to safe reply text")

    def clear_history(self):
        self._agent.clear_history_messages()
        while not self._message_queue.empty():
            self._message_queue.get_nowait()
        self._message_id_ = None
        self._save_history()

    def set_tz_offset(self, offset_hours):
        self._tz_offset = offset_hours

    def get_tz_offset(self):
        return self._tz_offset

    def get_last_image(self) -> str:
        return self._last_image
    
    def set_last_image(self, img: str):
        self._last_image = img

    async def reply_text(self, msg):
        if self._message_id_ is None:
            raise function_error.FunctionError(function_error.EC_RESET, "Reset")
        await self._sio.emit('text', msg, self._message_user_id_, self._session_id, self._message_id_)

    async def reply_image_base64(self, msg):
        if self._message_id_ is None:
            raise function_error.FunctionError(function_error.EC_RESET, "Reset")
        await self._sio.emit('image', msg, self._message_user_id_, self._session_id, self._message_id_)

    async def reply_markdown(self, md):
        if self._message_id_ is None:
            raise function_error.FunctionError(function_error.EC_RESET, "Reset")
        await self._sio.emit('markdown', md, self._message_user_id_, self._session_id, self._message_id_)

    async def push_notification(self, msg):
        if self._message_id_ is None:
            raise function_error.FunctionError(function_error.EC_RESET, "Reset")
        await self._sio.emit('notification', msg, self._message_user_id_, self._session_id, self._message_id_)

    def _save_history(self):
        if self._history_dir is None:
            return
        try:
            os.makedirs(self._history_dir, exist_ok=True)
            p = os.path.join(self._history_dir, self._session_id) + ".json"
            self._agent.save_history(p)
        except:
            pass

    def _load_history(self):
        if self._history_dir is None:
            return
        try:
            p = os.path.join(self._history_dir, self._session_id) + ".json"
            self._agent.load_history(p)
        except:
            pass
