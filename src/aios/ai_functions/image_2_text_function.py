# pylint:disable=E0402
import logging
from typing import Dict

from ..frame.compute_kernel import ComputeKernel
from ..proto.ai_function import *
from ..agent.llm_context import GlobaToolsLibrary

logger = logging.getLogger(__name__)

class Image2TextFunction(AIFunction):

    def __init__(self):
        self.func_id = "aigc.image_2_text"
        self.description = "According to the input image file address, return the description of the image content"
        self.parameters = ParameterDefine.create_parameters({
                "image_path": {"type": "string", "description": "image file path"}
            })
        logger.info(f"init Image2TextFunction")

    def register_function(self):
        GlobaToolsLibrary.get_instance().register_tool_function(self)

    def get_name(self) -> str:
        return self.func_id

    def get_description(self) -> str:
        return self.description

    def get_parameters(self) -> Dict:
        return self.parameters

    async def execute(self, **kwargs) -> str:
        logger.info(f"execute image_2_text function: {kwargs}")
        image_path = kwargs.get("image_path")
        data = await ComputeKernel.get_instance().do_image_2_text(image_path, '')
        try:
            result = data['message']['choices'][0]['message']['content']
        except (KeyError, TypeError, IndexError):
            logger.error(f"image_2_text error: {data}")
            result = ""
        return result


    def is_local(self) -> bool:
        return False

    def is_in_zone(self) -> bool:
        return True

    def is_ready_only(self) -> bool:
        return False


