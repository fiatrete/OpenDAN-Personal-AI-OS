from abc import ABC, abstractmethod
import aiofiles

class MediaReader(ABC):
    @abstractmethod
    async def read(self, inner_path:str,mode:str):
        pass


class FolderMediaReader(MediaReader):
    def __init__(self, root_dir:str) -> None:
        self.root_dir = root_dir
        pass

    async def read(self, inner_path:str,mode:str):
        full_path = self.root_dir + "/" + inner_path
        result_file = await aiofiles.open(full_path, mode,encoding='utf-8')
        return result_file