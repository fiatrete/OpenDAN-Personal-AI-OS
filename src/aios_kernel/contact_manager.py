from typing import List

class Contact:
    def __init__(self,name:str) -> None:
        self.name = name
        self.tags = []

    def is_zone_owner(self,zone_id=None) -> bool:
        return True

    def get_tags(self)->List[str]:
        return self.tags

    def get_name(self)->str:
        return self.name


class ContactManager:
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ContactManager()
        return cls._instance

    def __init__(self) -> None:
        self.contacts = {}
        self.contacts["liuzhicong"] = Contact("liuzhicong")

    #def get_by_addr(self,addr:str) -> Contact:
    #    pass

    def get_by_name(self,name:str) -> Contact:
        return self.contacts.get(name)