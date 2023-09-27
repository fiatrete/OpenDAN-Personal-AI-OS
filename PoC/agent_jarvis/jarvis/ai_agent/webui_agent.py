import contextlib
import json

import aiohttp

from jarvis import CFG
from jarvis.ai_agent.agent_utils import must_not_be_valid_json, get_thoughts, get_function, execute_function
from jarvis.ai_agent.base_agent import BaseAgent
from jarvis.functional_modules.functional_module import CallerContext, moduleRegistry
from jarvis.json_utils.json_fix_llm import fix_json_using_multiple_techniques
from jarvis.json_utils.utilities import validate_json
from jarvis.logger import logger


def _generate_system_prompt():
    return """Since now, every your response should satisfy the following JSON format, a 'function' must be chosen:
```
{
    "thoughts": {
        "text": "<Your thought>",
        "reasoning": "<Your reasoning, think step by step>",
        "speak": "<what you want to say to me>"
    },
    "function": {
        "name": "<mandatory, one of listed functions>",
        "args": {
            "arg name": "<value>"
        }
    }
}
```
I will ask you questions or ask you to do something. You should:
First, you should determine if you know the answer of the question or you can accomplish the task directly.
If so, you should response directly.
If not, you should try to complete the task by calling the functions below.
If you can't accomplish the task by yourself and no function is able to accomplish the task, say "Dear master, sorry, I'm not able to do that."

```
Available functions:
```
""" + moduleRegistry.to_prompt() + """
```
Your setup:
```
{
    "author": "OpenDAN",
    "name": "Jarvis",
}
Example:
```
Tom: generate a picture of me.
Jarvis: {
    "function": {
        "name": "stable_diffusion",
        "args": {
            "prompt": "me"
        }
    }
}
```
"""


def _generate_request(prompt: str):
    return {
        'prompt': prompt,
        'max_new_tokens': 1000,
        'do_sample': True,
        'temperature': 0.5,
        'top_p': 0.5,
        'typical_p': 1,
        'repetition_penalty': 1.18,
        'top_k': 40,
        'min_length': 0,
        'no_repeat_ngram_size': 0,
        'num_beams': 1,
        'penalty_alpha': 0,
        'length_penalty': 1,
        'early_stopping': False,
        'seed': -1,
        'add_bos_token': True,
        'truncation_length': 2048,
        'ban_eos_token': False,
        'skip_special_tokens': True,
        'stopping_strings': ["Tom: "]
    }


def _convert_role(role: str):
    if role == 'user':
        return 'Tom'
    if role == 'assistant':
        return 'Jarvis'
    return role


async def _completion(prompt):
    async with aiohttp.ClientSession() as session:
        # body = json.dumps(_generate_request(prompt))
        async with session.post(CFG.private_ai_address, json=_generate_request(prompt)) as response:
            if response.status == 200:
                resp_obj = await response.json()
                logger.debug(f"Completion result: {json.dumps(resp_obj, indent=2)}")
                result = resp_obj["results"][0]['text']
                return result

    return None


class WebuiAgent(BaseAgent):
    _system_prompt: str
    _history = []

    def __init__(self, context: CallerContext):
        super().__init__(context)
        self._system_prompt = _generate_system_prompt()

    async def feed_prompt(self, prompt):
        prompt = f'Tom: {prompt}'
        self._history.append(prompt)
        final_prompt = self._system_prompt + '\n' + '\n'.join(self._history)
        logger.debug(f"Final prompt: {final_prompt}")
        reply = await self._feed_prompt_to_get_respones(final_prompt)
        await self._handle_reply(reply)

    async def _feed_prompt_to_get_respones(self, prompt):
        assistant_reply = await _completion(prompt)

        reply = {
            "thoughts": None,
            "reasoning": None,
            "speak": None,
            "function": None,
            "arguments": None,
        }

        if must_not_be_valid_json(assistant_reply):
            raise Exception(f"AI replied an invalid response: {assistant_reply}!")
        else:
            assistant_reply_json = await fix_json_using_multiple_techniques(assistant_reply)

        # Print Assistant thoughts
        if assistant_reply_json != {}:
            validate_json(assistant_reply_json, "llm_response_format_1")
            try:
                get_thoughts(reply, assistant_reply_json)
                get_function(reply, assistant_reply_json)
            except Exception as e:
                logger.error(f"AI replied an invalid response: {assistant_reply}. Error: {str(e)}")
                raise e
        else:
            raise Exception(f"AI replied an invalid response: {assistant_reply}!")

        function_name = reply["function"]
        if function_name is None or function_name == '':
            raise Exception(f"Missing a function")
        arguments = reply["arguments"]

        if not isinstance(arguments, dict):
            raise Exception(f"Invalid arguments, it MUST be a dict")
        return reply

    async def _handle_reply(self, reply):
        # TODO: It's not reliable now, thus do nothing now.
        return
        if reply is None:
            await self._caller_context.reply_text("Sorry, but I don't understand what you want me to do.")
            return

        # Execute function
        function_name: str = reply["function"]
        arguments: dict = reply["arguments"]

        await self._caller_context.reply_text(reply["speak"])
        execute_error = None
        try:
            function_result = await execute_function(self._caller_context, function_name, **arguments)
        except Exception as e:
            function_result = "Failed"
            execute_error = e
        result = f"Function {function_name} returned: " f"{function_result}"

        if function_name is not None:
            if result is not None:
                self.append_history_message("system", result)
                logger.debug(f"SYSTEM: {result}")
            else:
                self.append_history_message("system", "Unable to execute function")
                logger.debug("SYSTEM: Unable to execute function")

        if execute_error is not None:
            raise execute_error

    def append_history_message(self, role: str, content: str):
        self._history.append({'role': role, 'content': content})

    def clear_history_messages(self):
        self._history.clear()

    def save_history(self, to_where):
        with open(to_where, "w") as f:
            s = json.dumps(self._history)
            f.write(s)

    def load_history(self, from_where):
        with contextlib.suppress(Exception):
            with open(from_where, "r") as f:
                self._history = json.loads(f.read())
