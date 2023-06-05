import asyncio
import contextlib
import json
import time
from typing import Dict, List

from openai.error import RateLimitError

from jarvis import CFG
from jarvis.ai_agent.agent_utils import must_not_be_valid_json, get_thoughts, get_function, execute_function, \
    create_chat_message
from jarvis.ai_agent.base_agent import BaseAgent
from jarvis.functional_modules.functional_module import CallerContext, moduleRegistry
from jarvis.gpt import token_counter, gpt
from jarvis.gpt.message import Message
from jarvis.json_utils.json_fix_llm import fix_json_using_multiple_techniques
from jarvis.json_utils.utilities import validate_json
from jarvis.logger import logger


def _generate_first_prompt():
    return """Since now, every your response should satisfy the following JSON format, a 'function' must be chosen:
```
{
    "thoughts": {
        "text": "<Your thought>",
        "reasoning": "<Your reasoning>",
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

Your setup:
```
{
    "author": "OpenDAN",
    "name": "Jarvis",
}
```
Available functions:
```
""" + moduleRegistry.to_prompt() + """
```
Example:
```
me: generate a picture of me.
you: {
    "thoughts": {
        "text": "You need a picture of 'me'",
        "reasoning": "stable_diffusion is able to generate pictures",
        "speak": "Ok, I will do that"
    },
    "function": {
        "name": "stable_diffusion",
        "args": {
            "prompt": "me"
        }
    }
}
```"""


class GptAgent(BaseAgent):
    _system_prompt: str
    _full_message_history: List[Message] = []
    _message_tokens: List[int] = []

    def __init__(self, caller_context: CallerContext):
        super().__init__(caller_context)
        self._system_prompt = _generate_first_prompt()
        logger.debug(f"Using GptAgent, system prompt is: {self._system_prompt}")

    async def _feed_prompt_to_get_response(self, prompt):
        assistant_reply = await self._chat_with_ai(
            self._system_prompt,
            prompt,
            CFG.token_limit,
        )

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

    async def feed_prompt(self, prompt):
        # Send message to AI, get response
        logger.debug(f"Trigger: {prompt}")
        reply: Dict = None
        # It seems that after the message is wrapped in JSON format, 
        # the probability that GPT will reply to the message in JSON format is much higher
        prompt = json.dumps({"message": prompt})
        for i in range(3):
            try:
                if i == 0:
                    reply = await self._feed_prompt_to_get_response(prompt)
                else:
                    reply = await self._feed_prompt_to_get_response(
                        prompt + ". Remember to reply using the specified JSON form")
                break
            except Exception as e:
                # TODO: Feed the error to ChatGPT?
                logger.debug(f"Failed to get reply, try again! {str(e)}")
                continue

        if reply is None:
            await self._caller_context.reply_text("Sorry, but I don't understand what you want me to do.")
            return

        # Execute function
        function_name: str = reply["function"]
        arguments: Dict = reply["arguments"]

        await self._caller_context.reply_text(reply["speak"])
        execute_error = None
        try:
            function_result = await execute_function(self._caller_context, function_name, **arguments)
        except Exception as e:
            function_result = "Failed"
            execute_error = e
        result = f"Function {function_name} returned: " f"{function_result}"

        if function_name is not None:
            # Check if there's a result from the function append it to the message
            # history
            if result is not None:
                self._caller_context.append_history_message("system", result)
                logger.debug(f"SYSTEM: {result}")
            else:
                self._caller_context.append_history_message("system", "Unable to execute function")
                logger.debug("SYSTEM: Unable to execute function")

        if execute_error is not None:
            raise execute_error

    def append_history_message(self, role: str, content: str):
        self._full_message_history.append({'role': role, 'content': content})
        self._message_tokens.append(-1)

    def clear_history_messages(self):
        self._full_message_history.clear()
        self._message_tokens.clear()

    def save_history(self, to_where):
        with open(to_where, "w") as f:
            assert len(self._message_tokens) == len(self._full_message_history)
            s = json.dumps([
                self._message_tokens,
                self._full_message_history,
            ])
            f.write(s)

    def load_history(self, from_where):
        with contextlib.suppress(Exception):
            with open(from_where, "r") as f:
                tmp = json.loads(f.read())
                if isinstance(tmp, list) and len(tmp[0]) == len(tmp[1]):
                    self._message_tokens = tmp[0]
                    self._full_message_history = tmp[1]

    async def _chat_with_ai(
            self, prompt, user_input, token_limit
    ):
        """Interact with the OpenAI API, sending the prompt, user input, message history,
        and permanent memory."""
        while True:
            try:
                model = CFG.llm_model
                # Reserve 1000 tokens for the response

                send_token_limit = token_limit - 1000

                (
                    next_message_to_add_index,
                    current_tokens_used,
                    insertion_index,
                    current_context,
                ) = await self._generate_context(prompt, model)

                current_tokens_used += await token_counter.count_message_tokens(
                    [create_chat_message("user", user_input)], model
                )  # Account for user input (appended later)

                while next_message_to_add_index >= 0:
                    # print (f"CURRENT TOKENS USED: {current_tokens_used}")
                    tokens_to_add = await self._get_history_message_tokens(next_message_to_add_index, model)
                    if current_tokens_used + tokens_to_add > send_token_limit:
                        break

                    message_to_add = self._full_message_history[next_message_to_add_index]
                    # Add the most recent message to the start of the current context,
                    #  after the two system prompts.
                    current_context.insert(insertion_index, message_to_add)

                    # Count the currently used tokens
                    current_tokens_used += tokens_to_add

                    # Move to the next most recent message in the full message history
                    next_message_to_add_index -= 1

                # Append user input, the length of this is accounted for above
                current_context.extend([create_chat_message("user", user_input)])

                # Calculate remaining tokens
                tokens_remaining = token_limit - current_tokens_used

                assert tokens_remaining >= 0

                async def on_single_chat_timeout(will_retry):
                    await self._caller_context.push_notification(
                        f'Thinking timeout{", retry" if will_retry else ", give up"}.')

                assistant_reply = await gpt.acreate_chat_completion(
                    model=model,
                    messages=current_context,
                    temperature=CFG.temperature,
                    max_tokens=tokens_remaining,
                    on_single_request_timeout=on_single_chat_timeout
                )

                # Update full message history
                self._caller_context.append_history_message("user", user_input)
                self._caller_context.append_history_message("assistant", assistant_reply)

                return assistant_reply
            except RateLimitError:
                # TODO: When we switch to langchain, or something else this is built in
                print("Error: ", "API Rate Limit Reached. Waiting 10 seconds...")
                await asyncio.sleep(10)

    async def _generate_context(self, prompt, model):
        # We use the timezone of the session
        timestamp = time.time() + time.timezone + self._caller_context.get_tz_offset() * 3600
        time_str = time.strftime('%c', time.localtime(timestamp))
        current_context = [
            create_chat_message("system", prompt),
            create_chat_message(
                "system", f"The current time and date is {time_str}"
            )
        ]

        # Add messages from the full message history until we reach the token limit
        next_message_to_add_index = len(self._full_message_history) - 1
        insertion_index = len(current_context)
        # Count the currently used tokens
        current_tokens_used = await token_counter.count_message_tokens(current_context, model)
        return (
            next_message_to_add_index,
            current_tokens_used,
            insertion_index,
            current_context,
        )

    async def _get_history_message_tokens(self, index, model: str = "gpt-3.5-turbo-0301") -> int:
        if self._message_tokens[index] == -1:
            # since couting token is relatively slow, we store it here
            self._message_tokens[index] = await token_counter.count_message_tokens([self._full_message_history[index]], model)
        return self._message_tokens[index]
