from typing import List

from jarvis import CFG
from jarvis.gpt import gpt
from jarvis.logger import logger


async def acall_ai_function(function: str, args: list, description: str, model: str | None = None) -> str:
    """Call an AI function

    This is a magic function that can do anything with no-code. See
    https://github.com/Torantulino/AI-Functions for more info.

    Args:
        function (str): The function to call
        args (list): The arguments to pass to the function
        description (str): The description of the function
        model (str, optional): The model to use. Defaults to None.

    Returns:
        str: The response from the function
    """
    if model is None:
        model = CFG.small_llm_model
    # For each arg, if any are None, convert to "None":
    args = [str(arg) if arg is not None else "None" for arg in args]
    # parse args to comma separated string
    args: str = ", ".join(args)
    messages: List[dict] = [
        {
            "role": "system",
            "content": f"You are now the following python function: ```# {description}"
                       f"\n{function}```\n\nOnly respond with your `return` value.",
        },
        {"role": "user", "content": args},
    ]

    logger.debug(str(messages))

    msg_type, msg_content = await gpt.acreate_chat_completion(model=model, messages=messages, temperature=0)
    if msg_type == "content":
        return msg_content
    return 'failed'
