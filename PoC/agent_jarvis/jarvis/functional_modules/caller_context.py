class CallerContext:
    __agent: 'BaseAgent' = None

    def __init__(self, agent):
        self.__agent = agent

    def append_history_message(self, role: str, content: str):
        self.__agent.append_history_message(role, content)

    def get_tz_offset(self):
        raise Exception("Function not implemented")

    def get_tz_offset_str(self):
        of = self.get_tz_offset()
        if of > 0:
            return f"+{of}"
        if of < 0:
            return f"{of}"
        return ""

    def get_last_image(self) -> str:
        raise NotImplementedError("Function not implemented")
    
    def set_last_image(self, img: str):
        raise NotImplementedError("Function not implemented")

    async def reply_text(self, msg):
        raise NotImplementedError("Function not implemented")

    async def reply_image_base64(self, msg):
        raise NotImplementedError("Function not implemented")

    async def reply_markdown(self, md):
        raise NotImplementedError("Function not implemented")

    async def push_notification(self, msg):
        raise NotImplementedError("Function not implemented")
