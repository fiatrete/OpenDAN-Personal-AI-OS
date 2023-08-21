
class pkg_info:
    def __init__(self) -> None:
        self.name = ""
        self.cid = None
        self.depends : list[str] = None
        self.author = None
        self.remote_urls = None
        self.target_media_type = "dir"
        self.source_media_type = "7z"

    @classmethod
    def parse_pkg_name(cls,pkg_name:str) -> Tuple[str, str, str]:
        """parse pkg name like test-pkg#nightly#>0.2.31#sha1:323423423 to test-pkg,nightly#>0.2.31,sha1:323423423"""
        pass
    


    @property
    def cid(self) -> str:
        return self.cid

class pkg_media_info:
    def __init__(self) -> None:
        pass



