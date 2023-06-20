import io
import base64
from typing import List

from jarvis.functional_modules.caller_context import CallerContext
from jarvis.functional_modules.functional_module import functional_module
from jarvis.logger import logger


def reg_or_not():
    try:
        from rembg import new_session, remove
        from PIL import Image
    except ImportError as e:
        logger.warn(f"rembg or PIL not installed, remove_bg will not be available")
        return

    session = new_session(model_name="u2net")

    @functional_module(
        name="remove_bg",
        description="Remove the background of last image",
        signature={})
    async def remove_bg(context: CallerContext):
        img_base64 = context.get_last_image()
        if img_base64 is None:
            await context.reply_text("You need to give me an image first")
            return "Failed"
        bytes_io = io.BytesIO(base64.b64decode(img_base64))
        img = Image.open(bytes_io)
        output = remove(img, session=session)
        output_bytesio = io.BytesIO()
        output.save(output_bytesio, 'PNG')
        output_bytes = output_bytesio.getvalue()
        result = base64.b64encode(output_bytes).decode()
        
        context.set_last_image(result)
        await context.reply_image_base64(result)
        return "Success"

reg_or_not()
