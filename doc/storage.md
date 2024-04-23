# NDN Storage

```python

class NDNStorage:
    async def get(self,data_name:str)->Dict:
        #return object desc, include local cache path

    async def set_file(self,local_path)->str:
        # return data_name

    async def read_content(self,data_name:str)->bytes:
        # return bytes
        # 这里不但会读取本地缓存，还会对内容进行验证

```