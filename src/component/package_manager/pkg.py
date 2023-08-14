
class pkg_info:
    def __init__(self) -> None:
        self.name = ""
        self.cid = None
        self.depends : list[str] = None
        pass
    
    def parse_pkg_name(pkg_name:str) -> Tuple[str, str, str]:
        #return pkg_id,version_str,cid
        pass
    
    @property
    def cid(self) -> str:
        return self.cid

class pkg_media_info:
    def __init__(self) -> None:
        pass



