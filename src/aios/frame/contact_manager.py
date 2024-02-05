from typing import List
import toml
import time
import logging

from datetime import datetime
from ..proto.agent_msg import AgentMsg
from ..proto.ai_function import ParameterDefine, SimpleAIFunction
from ..agent.llm_context import GlobaToolsLibrary
from .tunnel import AgentTunnel
from .contact import Contact


logger = logging.getLogger(__name__)    


class ContactManager:
    _instance = None
    @classmethod
    def get_instance(cls,filename=None) -> "ContactManager":
        if cls._instance is None:
            cls._instance = ContactManager(str(filename))
        return cls._instance
    
    def register_global_functions(self):
        gl = GlobaToolsLibrary.get_instance()

        get_parameters = ParameterDefine.create_parameters({"name":"contact name name"})
        gl.register_tool_function(SimpleAIFunction("system.contacts.get",
                                        "get contact info",
                                        self._get_contact,get_parameters))

        # todo: use json to save contact info
        update_parameters = ParameterDefine.create_parameters({"name":"name","contact_info":"A json to descrpit contact"})
        gl.register_tool_function(SimpleAIFunction("system.contacts.set",
                                        "set contact info",
                                        self._set_contact,update_parameters))

        return 



    def __init__(self, filename="contacts.toml"):
        self.filename = filename
        self.contacts = []

        self.is_auto_create_contact_from_telegram = True
    
    def load_data(self):
        try:
            with open(self.filename, "r") as f:
                config =  toml.load(f)
                return self.load_from_config(config)
        except FileNotFoundError:
            return {}
        
    def load_from_config(self,config_data:dict):
        self.contacts = [Contact.from_dict(item) for item in config_data.get("contacts", [])]

    def save_data(self):
        data = {
            "contacts": [contact.to_dict() for contact in self.contacts],
        }
        with open(self.filename, "w") as f:
            toml.dump(data, f)

    def set_contact(self, name:str, new_contact:Contact):
        assert name == new_contact.name
        for i, contact in enumerate(self.contacts):
            if contact.name == name:
                self.contacts[i] = new_contact
                self.save_data()
                return True
        for i, member in enumerate(self.family_members):
            if member.name == name:
                self.family_members[i] = new_contact
                self.save_data()
                return True
            
        return False

    def add_contact(self, name:str, new_contact:Contact):
        assert name == new_contact.name
        self.contacts.append(new_contact)
        self.save_data()

    def remove_contact(self, name:str):
        self.contacts = [contact for contact in self.contacts if contact.name != name]
        self.save_data()

    def find_contact_by_name(self, name:str):
        for contact in self.contacts:
            if contact.name == name:
                return contact
            
        return None
    
    def find_contact_by_telegram(self, telegram:str):
        for contact in self.contacts:
            if contact.telegram == telegram:
                return contact
         
        return None

    def find_contact_by_email(self, email:str):
        for contact in self.contacts:
            if contact.email == email:
                return contact

        return None

    def find_contact_by_phone(self, phone:str):
        for contact in self.contacts:
            if contact.phone == phone:
                return contact

        return None

    def list_contacts(self):
        return self.contacts
