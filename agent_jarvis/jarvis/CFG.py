import logging
import os
import dotenv

dotenv.load_dotenv()


# ==== Utils
def _string_to_bool(s: str | None):
    if s is None:
        return None
    s = s.lower()
    if s in ['y', 'yes', 't', 'true']:
        return True
    if s in ['n', 'no', 'f', 'false']:
        return False
    raise Exception(f"Invalid argument '{s}', should be a bool value: y/yes/n/no/t/true/f/false.")


def _string_to_log_level(s: str | None):
    if s is None:
        return None
    s = s.lower()
    if s in ['debug', 'd']:
        return logging.DEBUG
    if s in ['info', 'i']:
        return logging.INFO
    if s in ['w', 'warn', 'warning']:
        return logging.WARNING
    if s in ['error', 'e', 'err']:
        return logging.ERROR
    if s in ['fatal', 'critical']:
        return logging.FATAL
    raise Exception(f"Invalid argument '{s}', should be a log level: debug, info, warn, error, fatal")


def _get_env_str(name: str, must_not_empty: bool = False):
    v = os.getenv(name)
    if must_not_empty and (v is None or v == ''):
        raise Exception(f"Environment variable '{name}' is required!")
    return v


def _get_env_bool(name: str): return _string_to_bool(os.getenv(name))


def _get_env_int(name: str): return int(os.getenv(name))


def _get_env_float(name: str): return float(os.getenv(name))


def _get_env_log_level(name: str): return _string_to_log_level(os.getenv(name))


# The config

# DO NOT use it, it's still not mature yet
use_private_ai = _get_env_bool("JARVIS_USE_PRIVATE_AI") or False
private_ai_address = _get_env_str("JARVIS_PRIVATE_AI_URL", use_private_ai)

is_server_mode = _get_env_bool("JARVIS_SERVER_MODE") or False
# The port used in server mode
server_mode_port = _get_env_int("JARVIS_SERVER_MODE_PORT") or 1000
# Jarvis can also connect to a server as a client.
# This is the server's address
bot_server_url = _get_env_str("JARVIS_BOT_SERVER_URL") or "http://localhost:8081"

# The directory where the chat history should be stored,
# By storing the chat history, each time Jarvis starts up, the chat context is restored
chat_history_dir = _get_env_str("JARVIS_CHAT_HISTORY_DIR") or None

# ChatGPT temperature
temperature = _get_env_float("JARVIS_AI_TEMPERATURE") or 0

debug_mode = _get_env_bool("JARVIS_DEBUG_MODE") or False
log_level = _get_env_log_level("JARVIS_LOG_LEVEL") or logging.INFO

# The main llm model
llm_model = _get_env_str("JARVIS_LLM_MODEL") or "gpt-3.5-turbo-0301"
# The model used to handle some simple tasks
small_llm_model = _get_env_str("JARVIS_SMALL_LLM_MODEL") or "gpt-3.5-turbo-0301"
token_limit = _get_env_int("JARVIS_TOKEN_LIMIT") or 4000

openai_api_key = _get_env_str("JARVIS_OPENAI_API_KEY", True)
# If your service is not provided directly by openai,
# or you just deployed you own AI model with a same API as opeai.
# Or this configuration is useless
openai_url_base = _get_env_str("JARVIS_OPENAI_URL_BASE") or None

# Tell Jarvis where to load function modules
external_function_module_dirs = _get_env_str("JARVIS_EXTERNAL_FUNCTION_MODULE_DIR")

use_azure = False
def get_azure_deployment_id_for_model(model):
    assert False
    # TODO
