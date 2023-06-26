import io
import base64
from typing import List


def reg_or_not():
    try:
        from rembg import new_session, remove
        from PIL import Image
    except ImportError as e:
        logger.warn(f"rembg or PIL not installed, remove_bg will not be available")
        return

    session = new_session(model_name="u2net")
    if __name__ == "__main__":
        # If we run this script directly, download the model and exit
        return

    from jarvis.functional_modules.caller_context import CallerContext
    from jarvis.functional_modules.functional_module import functional_module
    from jarvis.logger import logger
    import threading
    from queue import Queue
    import asyncio

    class RembgThread:
        _task_queue: Queue
        _work_thread: threading.Thread

        def __init__(self) -> None:
            self._task_queue = Queue()
            self._work_thread = threading.Thread(target=self._work_thread_routine, daemon=True)
            self._work_thread.start()

        def _work_thread_routine(self):
            while True:
                img_base64, fut = self._task_queue.get()
                try:
                    bytes_io = io.BytesIO(base64.b64decode(img_base64))
                    img = Image.open(bytes_io)
                    output = remove(img, session=session)
                    output_bytesio = io.BytesIO()
                    output.save(output_bytesio, 'PNG')
                    output_bytes = output_bytesio.getvalue()
                    result = base64.b64encode(output_bytes).decode()
                    fut.set_result(result)
                except BaseException as ex:
                    if isinstance(ex, InterruptedError):
                        break
                    fut.set_exception(ex)
            logger.debug("Rembg thread exit")

        def add_task(self, img_base64: str):
            fut = asyncio.Future(loop=asyncio.get_event_loop())
            self._task_queue.put((img_base64, fut))
            return fut
    rembg_thread = RembgThread()

    @functional_module(
        name="remove_bg",
        description="Remove the background of last image",
        signature={})
    async def remove_bg(context: CallerContext):
        img_base64 = context.get_last_image()
        if img_base64 is None:
            await context.reply_text("You need to give me an image first")
            return "Failed"

        await context.reply_text("Removing the background, please wait")
        fut = rembg_thread.add_task(img_base64)
        result = await fut
        context.set_last_image(result)
        await context.reply_image_base64(result)
        return "Success"


reg_or_not()
