"""Utilities for the json_fixes package."""
import json
import re

from jsonschema import Draft7Validator

from jarvis import CFG
from jarvis.logger import logger


def extract_char_position(error_message: str) -> int:
    """Extract the character position from the JSONDecodeError message.

    Args:
        error_message (str): The error message from the JSONDecodeError
          exception.

    Returns:
        int: The character position.
    """

    char_pattern = re.compile(r"\(char (\d+)\)")
    if match := char_pattern.search(error_message):
        return int(match[1])
    else:
        raise ValueError("Character position not found in the error message.")


def validate_json(json_object: object, schema_name: object) -> object:
    """
    :type schema_name: object
    :param schema_name:
    :type json_object: object
    """
    with open(f"jarvis/json_utils/{schema_name}.json", "r") as f:
        schema = json.load(f)
    validator = Draft7Validator(schema)

    if errors := sorted(validator.iter_errors(json_object), key=lambda e: e.path):
        logger.debug("The JSON object is invalid.")
        if CFG.debug_mode:
            # Replace 'json_object' with the variable containing the JSON data
            logger.debug(json.dumps(json_object, indent=4))
            logger.debug("The following issues were found:")

            for error in errors:
                logger.debug(f"Error: {error.message}")
    elif CFG.debug_mode:
        logger.debug("The JSON object is valid.")

    return json_object
