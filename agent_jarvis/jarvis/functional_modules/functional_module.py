import json
import traceback
from typing import Callable, Any, Tuple, Dict, List

from jarvis.functional_modules.caller_context import CallerContext
from jarvis.logger import logger
from jarvis.utils import function_error
from jarvis import CFG


class FunctionalModule:
    name: str
    description: str
    method: Callable[..., Any]
    signature: dict[str, dict]

    def __init__(self, name, description, method, signature):
        self.name = name
        self.description = description
        self.method = method
        self.signature = signature


class FunctionalModuleRegistry:
    _modules: Dict[str, FunctionalModule] = {}

    def __init__(self):
        pass

    def register(self, cmd):
        self._modules.update({cmd.name: cmd})

    def print(self):
        for cmd in self._modules.values():
            print(json.dumps({
                "name": cmd.name,
                "description": cmd.description,
                "signature": cmd.signature
            }))

    @staticmethod
    def _signature_to_string(signature: dict[str, dict]):
        return ", ".join([f"{k}: <{v['description']}>" for k, v in signature.items()])

    def to_prompt(self):
        text = ""
        i = 1
        for module in sorted(self._modules.values(), key=lambda cmd: cmd.name):
            if module.signature is None or len(module.signature) == 0:
                text += f"{i}. {module.name}: {module.description}, don't need argument\n"
            else:
                text += f"{i}. {module.name}: {module.description}, args: {FunctionalModuleRegistry._signature_to_string(module.signature)}\n"
            i += 1
        if len(text) > 0:
            text = text[0:-1]  # Delete the tailing '\n'

        return text

    def to_json_schema(self):
        return [
            {
                "name": module.name,
                "description": module.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        key: {
                            k: v for k, v in value.items() if k != "required"
                        }
                        for key, value in module.signature.items()
                    },
                    "required": [key for key, value in module.signature.items() if value.get("required") != False]
                }

            }
            for module in sorted(self._modules.values(), key=lambda cmd: cmd.name)
        ]

    async def execute_function(self, context: CallerContext, function_name: str, **kwargs):
        cmd = self._modules.get(function_name)
        if cmd is not None:
            return await cmd.method(context, **kwargs)
        return "(Module Not Found)"


moduleRegistry = FunctionalModuleRegistry()


def functional_module(name: str,
                      description: str,
                      signature: dict[str, dict] = None):
    if signature is None:
        signature = {}

    def decorator(func: Callable[..., Any]):
        async def wrapper(context: CallerContext, *args, **kwargs) -> Any:
            try:
                return await func(context, *args, **kwargs)
            except function_error.FunctionError as e:
                logger.error(traceback.format_exc())
                await context.reply_text(f"Sorry, failed to do the job: {e.msg}")
            except:
                logger.error(traceback.format_exc())
                await context.reply_text("Sorry, an unknown error occurred during doing the job")
            return "Failed"

        cmd = FunctionalModule(
            name=name,
            description=description,
            method=wrapper,
            signature=signature
        )

        global moduleRegistry
        moduleRegistry.register(cmd)
        if CFG.debug_mode:
            print("Registering: " + name)

        return wrapper

    return decorator
