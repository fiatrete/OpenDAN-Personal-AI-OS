import asyncio

import openai
from openai.error import RateLimitError, APIError, Timeout

from jarvis import CFG
from jarvis.logger import logger
from typing import Callable

openai.api_key = CFG.openai_api_key
if CFG.openai_url_base is not None:
    openai.api_base = CFG.openai_url_base

print_total_cost = CFG.debug_mode


async def acreate_chat_completion_once(
        messages: list,  # type: ignore
        model: str | None = None,
        temperature: float = CFG.temperature,
        max_tokens: int | None = None,
        deployment_id=None,
        request_timeout=40,
        **kwargs
) -> str:
    """
    Create a chat completion and update the cost.
    Args:
    messages (list): The list of messages to send to the API.
    model (str): The model to use for the API call.
    temperature (float): The temperature to use for the API call.
    max_tokens (int): The maximum number of tokens for the API call.
    Returns:
    str: The AI's response.
    """
    if deployment_id is not None:
        response = await openai.ChatCompletion.acreate(
            deployment_id=deployment_id,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
            **kwargs
        )
    else:
        response = await openai.ChatCompletion.acreate(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
            **kwargs
        )
    if CFG.debug_mode:
        logger.debug(f"Response: {response}")
    # prompt_tokens = response.usage.prompt_tokens
    # completion_tokens = response.usage.completion_tokens
    return response


# Overly simple abstraction until we create something better
# simple retry mechanism when getting a rate error or a bad gateway
async def acreate_chat_completion(
        messages: list[dict],
        model: str = None,
        temperature: float = CFG.temperature,
        max_tokens: int = None,
        request_timeout: int = 40,
        num_retries=3,
        on_single_request_timeout: Callable = None,
        **kwargs
):
    """Create a chat completion using the OpenAI API

    Args:
        messages (List[dict]): The messages to send to the chat completion
        model (str, optional): The model to use. Defaults to None.
        temperature (float, optional): The temperature to use. Defaults to 0.9.
        max_tokens (int, optional): The max tokens to use. Defaults to None.
        request_timeout (int, optional): The request_timeout of a single openai request.
        num_retries (int, optional): The max retries.
        on_single_request_timeout (Callable, optional): This function will be called each time a single openai request
            timeout, must be an async function, the last timeout will not emit callback.

    Returns:
        str: The response from the chat completion
    """
    if CFG.debug_mode:
        logger.debug(
            f"Creating chat completion with model {model}, temperature {temperature}, max_tokens {max_tokens}"
        )

    response = None

    for attempt in range(num_retries):
        backoff = min(2 ** (attempt + 2), 8)
        try:
            if CFG.use_azure:
                response = await acreate_chat_completion_once(
                    deployment_id=CFG.get_azure_deployment_id_for_model(model),
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    request_timeout=request_timeout,
                    **kwargs
                )
            else:
                response = await acreate_chat_completion_once(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    request_timeout=request_timeout,
                    **kwargs
                )
            break
        except RateLimitError:
            if CFG.debug_mode:
                logger.debug(f"Error: Reached rate limit, passing...")
        except (APIError, Timeout) as e:
            if isinstance(e, Timeout):
                if on_single_request_timeout:
                    await on_single_request_timeout(num_retries < num_retries - 1)
            if e.http_status != 502:
                raise
            if attempt == num_retries - 1:
                raise
        if CFG.debug_mode:
            logger.debug(
                f"Error: API Bad gateway. Waiting {backoff} seconds..."
            )
        await asyncio.sleep(backoff)
    if response is None:
        logger.error(f"Failed to get response from GPT after {num_retries} retries")
        raise RuntimeError(f"Failed to get response after {num_retries} retries")

    choice_message = response.choices[0].message
    content = choice_message.get("content")
    if content is None:
        return "function_call", {k: v for k, v in choice_message["function_call"].items()}
    else:
        return "content", content
