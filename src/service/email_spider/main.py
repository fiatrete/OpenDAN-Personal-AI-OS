import asyncio
from .spider import EmailSpider, EmailConverter


if __name__ == "__main__":
    spider = EmailSpider("smtp.163.com","user","pwd","./email")
    asyncio.run(spider.run())

    converter = EmailConverter("./email",KnowledgeBase())
    asyncio.run(converter.run())

    
