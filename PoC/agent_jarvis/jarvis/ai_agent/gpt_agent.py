import asyncio
import contextlib
import json
import time
from typing import Dict, List

from openai.error import RateLimitError

from jarvis import CFG
from jarvis.ai_agent.agent_utils import must_not_be_valid_json, get_thoughts, get_function, execute_function
from jarvis.ai_agent.base_agent import BaseAgent
from jarvis.functional_modules.functional_module import CallerContext, moduleRegistry
from jarvis.gpt import token_counter, gpt
from jarvis.json_utils.json_fix_llm import fix_json_using_multiple_techniques
from jarvis.json_utils.utilities import validate_json
from jarvis.logger import logger


def _generate_first_prompt():
    return """I will ask you questions or ask you to do something. You should:
First, determine if you know the answer of the question or you can accomplish the task directly. 
If so, response directly. 
If not, try to complete the task by calling the functions below.
If you can't accomplish the task by yourself and no function is able to accomplish the task, say "Dear master, sorry, I'm not able to do that."

Your setup:
```
{
    "author": "OpenDAN",
    "name": "Jarvis",
}
```"""


class GptAgent(BaseAgent):
    _system_prompt: str
    _full_message_history: List[dict] = []
    _message_tokens: List[int] = []

    def __init__(self, caller_context: CallerContext):
        super().__init__(caller_context)
        self._system_prompt = _generate_first_prompt()
        logger.debug(f"Using GptAgent, system prompt is: {self._system_prompt}")
        logger.debug(f"{json.dumps(moduleRegistry.to_json_schema())}")

    async def _feed_prompt_to_get_response(self, prompt):
        reply_type, assistant_reply = await self._chat_with_ai(
            self._system_prompt,
            prompt,
            CFG.token_limit,
        )

        if reply_type == "content":
            return {
                "speak": assistant_reply,
            }
        elif reply_type == "function_call":
            arguments_string = assistant_reply["arguments"]
            try:
                arguments = json.loads(arguments_string)
            except:
                arguments = await fix_json_using_multiple_techniques()
            return {
                "function": assistant_reply["name"],
                "arguments": arguments
            }

    async def feed_prompt(self, prompt):
        # Send message to AI, get response
        logger.debug(f"Trigger: {prompt}")
        reply: Dict = None
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
        function_name: str = reply.get("function")
        if function_name is None:
            await self._caller_context.reply_text(reply["speak"])
        else:
            arguments: Dict = reply["arguments"]

            function_result = "Failed"
            try:
                function_result = await execute_function(self._caller_context, function_name, **arguments)
            finally:
                result = f"{function_result}"

                # Check if there's a result from the function append it to the message
                # history
                if result is not None:
                    self.append_history_message_raw({"role": "function", "name": function_name, "content": result})
                    logger.debug(f"function: {result}")
                else:
                    self.append_history_message_raw({"role": "function", "name": function_name, "content": "Unable to execute function"})
                    logger.debug("function: Unable to execute function")

    def append_history_message(self, role: str, content: str):
        self._full_message_history.append({'role': role, 'content': content})
        self._message_tokens.append(-1)

    def append_history_message_raw(self, msg: dict):
        self._full_message_history.append(msg)
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
                    [{"role": "user", "content": user_input}], model
                )  # Account for user input (appended later)

                # TODO: OpenAI does not say how to count function tokens, we use this method to roughly get the tokens count
                #   It's result looks much larger than OpenAI's result
                current_tokens_used += await token_counter.count_message_tokens(
                    [{"role": "user", "content": json.dumps(moduleRegistry.to_json_schema())}], model
                )

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
                current_context.extend([{"role": "user", "content": user_input}])

                # Calculate remaining tokens
                tokens_remaining = token_limit - current_tokens_used

                assert tokens_remaining >= 0

                async def on_single_chat_timeout(will_retry):
                    await self._caller_context.push_notification(
                        f'Thinking timeout{", retry" if will_retry else ", give up"}.')


                reply_type, assistant_reply = await gpt.acreate_chat_completion(
                    model=model,
                    messages=current_context,
                    temperature=CFG.temperature,
                    max_tokens=tokens_remaining,
                    on_single_request_timeout=on_single_chat_timeout,
                    functions=moduleRegistry.to_json_schema()
                )

                # Update full message history
                if reply_type == "content":
                    self.append_history_message("user", user_input)
                    self.append_history_message("assistant", assistant_reply)
                    pass
                elif reply_type == "function_call":
                    self.append_history_message("user", user_input)
                    self.append_history_message_raw({"role": "assistant", "function_call": assistant_reply, "content": None})
                    pass
                else:
                    assert False, "Unexpected reply type"

                return reply_type, assistant_reply
            except RateLimitError:
                # TODO: When we switch to langchain, or something else this is built in
                print("Error: ", "API Rate Limit Reached. Waiting 10 seconds...")
                await asyncio.sleep(10)

    async def _generate_context(self, prompt, model):
        # We use the timezone of the session
        timestamp = time.time() + time.timezone + self._caller_context.get_tz_offset() * 3600
        time_str = time.strftime('%c', time.localtime(timestamp))
        current_context = [
            {"role": "system", "content": prompt},
            {"role": "system", "content": f"The current time and date is {time_str}"},
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
