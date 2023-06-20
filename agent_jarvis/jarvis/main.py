import asyncio
import os
import sys
import time

from jarvis import CFG
from jarvis.logger import logger
from pathlib import Path

from aiohttp import web
import socketio
import socketio.exceptions

import importlib.util
from importlib.machinery import SourceFileLoader
from jarvis.gateway.session import Session, SioServerConnection, SioClientConnection
from jarvis.utils.incoming_chat_message_parser import parse_incoming_chat_message


def _import_external_functions():
    def import_recursive(path: str):
        files = os.listdir(path)
        no_subdir = False
        for file in files:
            if file.endswith(".module.py"):
                # If a module file exists, then it's the only module we are going to load
                full_path = os.path.join(path, file)
                # Add the module path
                sys.path.append(os.path.dirname(full_path))
                SourceFileLoader(full_path, full_path).load_module()
                no_subdir = True

        if not no_subdir:
            # This is not the root of a module, let's dig in
            for file in files:
                full_path = os.path.join(path, file)
                if os.path.isdir(full_path):
                    import_recursive(full_path)

    import_recursive(CFG.external_function_module_dirs)


def _import_functions():
    py_files = []
    dir_path = os.path.join(Path(__file__).parent, "functional_modules")
    for file in os.listdir(dir_path):
        if file.endswith(".py"):
            py_files.append(file)

    for file in py_files:
        if file == "functional_module.py" or file == "caller_context.py":
            continue
        SourceFileLoader(file, os.path.join("jarvis/functional_modules", file)).load_module()

    _import_external_functions()


logger.info("Registering functions...")
_import_functions()


def run_server_mode():
    logger.info("Starting server...")

    async def index(request):
        """Serve the client-side application."""
        with open('./TestPage/index.html') as f:
            return web.Response(text=f.read(), content_type='text/html')

    app = web.Application()
    session_map = {}

    sio: socketio.AsyncServer = socketio.AsyncServer(
        max_http_buffer_size=50000000,  # 50M
    )
    sio.attach(app)

    @sio.event
    def connect(sid, environ):
        logger.debug(f"connect {sid}")
        session_map.update({sid: Session(SioServerConnection(sio, sid), sid)})

    @sio.event
    async def disconnect(sid):
        logger.debug(f'disconnect {sid}')
        session: Session = session_map[sid]
        session_map.update({sid: None})
        await session.stop()

    @sio.on('chat_message')
    async def chat_message(sid, data):
        logger.debug(f"message {data}")
        msg = parse_incoming_chat_message(data)
        if msg is None:
            return

        session = session_map[sid]
        if session is None:
            logger.debug(f"Error: session {sid} not found!")
            return

        if msg.message_type == 'clear':
            session.clear_history()
        elif msg.message_type == 'set_ts_offset':
            offset = int(msg.message_content)
            if offset > 12 or offset < -12:
                logger.error(f"Invalid tz offset: {msg.message_content}")
                return
            session.set_tz_offset(offset)
        elif msg.message_type == 'text':
            await session.on_chat_message(msg)
        elif msg.message_type == 'image':
            session.set_last_image(msg.message_content)

    app.router.add_static('/js', './TestPage/js')
    app.router.add_static('/css', './TestPage/css')
    app.router.add_get('/', index)
    web.run_app(app, host='0.0.0.0', port=CFG.server_mode_port)


async def run_client_mode(session_map: dict[str, Session]):
    sio = socketio.AsyncClient()
    # The connection is re-established, thus re-set sio of all sessions.
    for s in session_map.values():
        s.set_sio(SioClientConnection(sio))

    # @sio.event
    @sio.on('connect')
    def connect():
        logger.debug(f"connected")

    @sio.event
    def disconnect():
        logger.debug(f'disconnected')
        # Do nothing, sessions will not be proactively destoryed in this mode.

    @sio.on('chat_message')
    async def chat_message(data):
        logger.debug(f"message {data}")
        msg = parse_incoming_chat_message(data)
        if msg is None:
            return
        sid = msg.chat_id
        if sid in session_map.keys():
            session = session_map[sid]
            assert session is not None
        else:
            session = Session(SioClientConnection(sio), sid)
            session_map.update({sid: session})

        if msg.message_type == 'clear':
            session.clear_history()
        elif msg.message_type == 'set_ts_offset':
            offset = int(msg.message_content)
            if offset > 12 or offset < -12:
                logger.error(f"Invalid tz offset: {msg.message_content}")
                return
            session.set_tz_offset(offset)
        elif msg.message_type == 'text':
            await session.on_chat_message(msg)
        elif msg.message_type == 'image':
            session.set_last_image(msg.message_content)

    await sio.connect(CFG.bot_server_url)
    try:
        await sio.wait()
    except:
        # I don't known why, but if we don't catch here, the logger.debug below will 
        # die when the program is interrupted by SIGINT
        raise
    finally:
        del sio
        logger.debug("Client mode end")


async def run_client_mode_async(session_map: dict[str, Session]):
    while True:
        try:
            await run_client_mode(session_map)
        except (InterruptedError, asyncio.CancelledError):
            logger.info(f"Interrupted, exit...")
            break
        except BaseException as e:
            logger.error(f"Failed to run in client mode, try again 1 seconds later: {str(e)}")
            await asyncio.sleep(1)


def main():
    if CFG.is_server_mode:
        run_server_mode()
    else:
        session_map = {}
        asyncio.run(run_client_mode_async(session_map))


if __name__ == '__main__':
    main()

logger.debug("End jarvis")
