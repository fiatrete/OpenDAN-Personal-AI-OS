import json

from jarvis.logger import logger


class IncomingChatMessage:
    user_id: str = None
    chat_id: str = None
    message_type: str = None
    message_content: str = None
    message_id: str = None

    def __init__(self):
        pass


def parse_incoming_chat_message(data: str | dict):
    """
    The expected format of data is
    {
      user: {
        id: string
      }
      chat: {
        id: string
      }
      message: {
        type: 'text' | 'voice' | ...
        content: string
        id: string
      }
    }
    """
    result = IncomingChatMessage()
    try:
        if isinstance(data, dict):
            obj = data
        else:
            obj = json.loads(data)
        result.user_id = obj["user"]["id"]
        result.chat_id = obj["chat"]["id"]
        result.message_type = obj["message"]["type"]
        result.message_id = obj["message"]["id"]
        result.message_content = obj["message"]["content"]
        # TODO: Check if they are str
        return result
    except Exception as e:
        logger.debug(f"An invalid message from session: {data}")
        return None


def assemble_json_message(msg_type: str, msg: str, user_id: str, session_id: str, message_id: str):
    return {
        "user": {
            "id": user_id
        },
        "chat": {
            "id": session_id
        },
        "message": {
            "type": msg_type,
            "content": msg,
            "id": message_id
        }
    }
