from typing import List

class NamedObjectStorage:
    def __init__(self, storage, name: str):
        self.storage = storage
        self.name = name

    async def get(self, key: str) -> bytes:
        return await self.storage.get(self.name, key)

    async def put(self, key: str, data: bytes):
        await self.storage.put(self.name, key, data)

    async def delete(self, key: str):
        await self.storage.delete(self.name, key)

    async def list(self) -> List[str]:
        return await self.storage.list(self.name)