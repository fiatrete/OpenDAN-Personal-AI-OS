from aios_kernel.knowledge import KnowledgeBase, EmailObject

# define a email converter class

class EmailConverter:
    # define init method
    def __init__(self, local_dir, knowledge_base: KnowledgeBase) -> None:
        pass

    async def run(self):
        # convert the email to knowledge object
        for email_dir in self._next():
            # convert the email to knowledge object
            knowledge_object = self._convert(email_dir)
            # insert the knowledge object to knowledge base
            await self.knowledge_base.insert(knowledge_object)

    def _next(self) -> str:
        pass

    def _convert(self, email_dir) -> EmailObject:
        pass

    