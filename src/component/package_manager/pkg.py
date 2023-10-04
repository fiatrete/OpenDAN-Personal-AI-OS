from typing import Tuple


class PackageInfo:
    def __init__(self) -> None:
        self.name = ""
        self.cid = None
        self.depends : list[str] = None
        self.author = None
        self.remote_urls = None
        self.target_media_type = "dir"
        self.source_media_type = "7z"

    @staticmethod
    def parse_pkg_name(pkg_name:str) -> Tuple[str, str, str]:
        """parse pkg name like test-pkg#nightly~>0.2.31#sha1:323423423 to test-pkg,nightly#>0.2.31,sha1:323423423"""
        args = pkg_name.split("#")
        if len(args) == 1:
            return args[0],None,None
        elif len(args) == 2:  
            return args[0],None,arg[2]
        elif len(args) == 3:
            return args[0],args[1],args[2]
        else:
            logger.error(f"parse pkg name {pkg_name} failed!")
            return None,None,None

    


    @property
    def cid(self) -> str:
        return self.cid

class PackageMediaInfo:
    def __init__(self,full_path,media_type) -> None:
        self.media_type = media_type
        self.full_path = full_path



