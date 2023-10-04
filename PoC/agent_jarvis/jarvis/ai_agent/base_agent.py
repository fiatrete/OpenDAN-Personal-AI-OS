from jarvis.functional_modules.functional_module import CallerContext


class BaseAgent:
    _caller_context: CallerContext = None

    def __init__(self, context: CallerContext):
        self._caller_context = context

    async def feed_prompt(self, prompt):
        raise NotImplementedError("Not implemented")

    def append_history_message(self, role: str, content: str):
        raise NotImplementedError("Not implemented")

    def clear_history_messages(self):
        raise NotImplementedError("Not implemented")

    def save_history(self, to_where):
        raise NotImplementedError("Not implemented")

    def load_history(self, from_where):
        raise NotImplementedError("Not implemented")
