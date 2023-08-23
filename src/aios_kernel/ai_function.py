class ai_function:
    def __init__(self) -> None:
        self.intro : str = None
    
    def load_from_config(self,config:dict) -> bool:
        pass

    def is_local(self) -> bool:
        pass

    def is_in_zone(self) -> bool:
        pass
    
    def is_readyonly(self) -> bool:
        pass

    def get_intro(self) -> str:
        return self.intro
    
    async def execute(self):
        pass

# call chain is a combination of ai_function,group of ai_function.
class call_chain:
    def __init__(self) -> None:
        pass

    def load_from_config(self,config:dict) -> bool:
        pass

    async def execute(self):
        pass