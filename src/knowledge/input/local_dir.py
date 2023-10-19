import os
import aiofiles
import chardet
from knowledge import ImageObjectBuilder, DocumentObjectBuilder, KnowledgeBase

class KnowledgeDirSource:
    def __init__(self, config):
        self.config = config
        config["path"] = os.path.abspath(config["path"])

    # @classmethod
    # def user_config_items(cls):
    #     return [("path", "local dir path")]

    def path(self):
        return self.config["path"]
    
    @staticmethod
    async def read_txt_file(file_path:str)->str:
        cur_encode = "utf-8"
        async with aiofiles.open(file_path,'rb') as f:
            cur_encode = chardet.detect(await f.read())['encoding']
        
        async with aiofiles.open(file_path,'r',encoding=cur_encode) as f:
            return await f.read()
        
    async def next(self):
        # logging.debug(f"knowledge dir source {self.id()} run once")
        # journal_client = KnowledgeJournalClient()
        # latest_journal = journal_client.latest_journal(self.id())
        # if latest_journal is not None:
        #     if os.path.getmtime(self.path()) <= latest_journal.timestamp:
        #         logging.debug(f"knowledge dir source {self.id()} ingnored for no update")
        #         return
        while True:
            file_pathes = sorted(os.listdir(self.path()), key=lambda x: os.path.getctime(os.path.join(self.path(), x)))
            for rel_path in file_pathes:
                file_path = os.path.join(self.path(), rel_path)
                # timestamp = os.path.getctime(file_path)
                # if latest_journal is not None:
                #     if timestamp <= latest_journal.timestamp:
                #         continue
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    # logging.info(f"knowledge dir source {self.id()} found image file {file_path}")
                    image = ImageObjectBuilder({}, {}, file_path).build()
                    await KnowledgeBase().insert_object(image)
                    yield image.calculate_id()
                    # journal_client.insert(KnowledgeJournal("dir", self.id(), rel_path, str(image.calculate_id()), timestamp))
                if ext in ['.txt']:
                    # logging.info(f"knowledge dir source {self.id()} found text file {file_path}")
                    text = await self.read_txt_file(file_path)
                    document = DocumentObjectBuilder({}, {}, text).build()
                    await KnowledgeBase().insert_object(document)
                    yield document.calculate_id()
                    # journal_client.insert(KnowledgeJournal("dir", self.id(), rel_path, str(document.calculate_id()), timestamp))
            yield 0
            

def init(params: dict) -> KnowledgeDirSource:
    return KnowledgeDirSource(params)