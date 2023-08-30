# define a email spider class

class EmailSpider:
    def __init__(self, address, account, pwd, local_dir) -> None:
        pass

    async def run(self): 
        # spide the email from the email server
        for email_link in self._next():
            # save the email to local directory
            self._save(email_link)

    def _next(self):
        pass

    def _save(self, email_link) -> str:
        pass