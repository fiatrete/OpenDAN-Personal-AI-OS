import json
from typing import Dict

from jarvis.functional_modules.functional_module import CallerContext, moduleRegistry
from jarvis.logger import logger


def must_not_be_valid_json(s: str):
    """
    Simply check if the string is a JSON.
    If the string does not contain even 1 pair of '{}',
    it must not be a JSON, we treat it as a normal string.
    """
    if s.count('{') < 1 and s.count("{") < 1:
        return True
    return False

def get_thoughts(reply: Dict, assistant_reply_json_valid: dict):
    assistant_thoughts_reasoning = None
    assistant_thoughts_speak = None

    assistant_thoughts = assistant_reply_json_valid.get("thoughts", {})
    assistant_thoughts_text = assistant_thoughts.get("text")
    if assistant_thoughts:
        assistant_thoughts_reasoning = assistant_thoughts.get("reasoning")
        assistant_thoughts_speak = assistant_thoughts.get("speak")
    reply["thoughts"] = assistant_thoughts_text
    reply["reasoning"] = assistant_thoughts_reasoning
    reply["speak"] = assistant_thoughts_speak
    logger.debug(f" THOUGHTS: {assistant_thoughts_text}")
    logger.debug(f"REASONING: {assistant_thoughts_reasoning}")
    logger.debug(f" SPEAKING: {assistant_thoughts_speak}")


def get_function(reply: Dict, response_json: Dict):
    try:
        if "function" not in response_json:
            return "Error:", "Missing 'function' object in JSON"

        if not isinstance(response_json, dict):
            return "Error:", f"'response_json' object is not dictionary {response_json}"

        function = response_json["function"]
        if not isinstance(function, dict):
            return "Error:", "'function' object is not a dictionary"

        if "name" not in function:
            return "Error:", "Missing 'name' field in 'function' object"

        function_name = function["name"]

        # Use an empty dictionary if 'args' field is not present in 'function' object
        arguments = function.get("args", {})

        reply["function"] = function_name
        reply["arguments"] = arguments

        return function_name, arguments
    except json.decoder.JSONDecodeError:
        return "Error:", "Invalid JSON"
    except Exception as e:
        return "Error:", str(e)


async def execute_function(
        context: CallerContext,
        function_name: str,
        **arguments,
):
    logger.debug(f"Executing function: {function_name}({arguments})")
    await context.push_notification(f"Executing function: {function_name}({arguments})")
    return await moduleRegistry.execute_function(context, function_name, **arguments)
