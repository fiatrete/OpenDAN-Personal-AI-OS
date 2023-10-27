import os
import aiofiles
import chardet
import logging
import string
from knowledge import ImageObjectBuilder, DocumentObjectBuilder, KnowledgePipelineEnvironment, KnowledgePipelineJournal
from aios_kernel.storage import AIStorage

class KnowledgeDirSource:
    def __init__(self, env: KnowledgePipelineEnvironment, config):
        self.env = env
        path = string.Template(config["path"]).substitute(myai_dir=AIStorage.get_instance().get_myai_dir())
        config["path"] = path
        self.config = config  

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
        while True:
            journals = self.env.journal.latest_journals(1)
            from_time = 0
            if len(journals) == 1:
                latest_journal = journals[0]
                if latest_journal.is_finish():
                    yield None
                    continue
                from_time = os.path.getctime(latest_journal.get_input())
                if os.path.getmtime(self.path()) <= from_time:
                    yield (None, None)
                    continue
            
            file_pathes = sorted(os.listdir(self.path()), key=lambda x: os.path.getctime(os.path.join(self.path(), x)))
            for rel_path in file_pathes:
                file_path = os.path.join(self.path(), rel_path)
                timestamp = os.path.getctime(file_path)
                if timestamp <= from_time:
                    continue
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    logging.info(f"knowledge dir source found image file {file_path}")
                    image = ImageObjectBuilder({}, {}, file_path).build(self.env.get_knowledge_store())
                    await self.env.get_knowledge_store().insert_object(image)
                    yield (image.calculate_id(), file_path)
                if ext in ['.txt']:
                    logging.info(f"knowledge dir source found text file {file_path}")
                    text = await self.read_txt_file(file_path)
                    document = DocumentObjectBuilder({}, {}, text).build(self.env.get_knowledge_store())
                    await self.env.get_knowledge_store().insert_object(document)
                    yield (document.calculate_id(), file_path)
            yield (None, None)
            

def init(env: KnowledgePipelineEnvironment, params: dict) -> KnowledgeDirSource:
    return KnowledgeDirSource(env, params)