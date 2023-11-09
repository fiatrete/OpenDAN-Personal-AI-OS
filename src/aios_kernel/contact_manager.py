from typing import List
import toml
import time
from datetime import datetime
from .agent_base import AgentMsg
from .tunnel import AgentTunnel
from .contact import Contact,FamilyMember
import logging

logger = logging.getLogger(__name__)    


class ContactManager:
    _instance = None
    @classmethod
    def get_instance(cls,filename=None) -> "ContactManager":
        if cls._instance is None:
            cls._instance = ContactManager(str(filename))
        return cls._instance

    def __init__(self, filename="contacts.toml"):
        self.filename = filename
        self.contacts = []
        self.family_members = []    

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
        self.family_members = [FamilyMember.from_dict(item) for item in config_data.get("family_members", [])]
    
    def save_data(self):
        data = {
            "contacts": [contact.to_dict() for contact in self.contacts],
            "family_members": [member.to_dict() for member in self.family_members]
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
            
        for member in self.family_members:
            if member.name == name:
                return member
        return None
    
    def find_contact_by_telegram(self, telegram:str):
        for contact in self.contacts:
            if contact.telegram == telegram:
                return contact
        for member in self.family_members:
            if member.telegram == telegram:
                return member            
        return None

    def find_contact_by_email(self, email:str):
        for contact in self.contacts:
            if contact.email == email:
                return contact
        for member in self.family_members:
            if member.email == email:
                return member   
        return None

    def find_contact_by_phone(self, phone:str):
        for contact in self.contacts:
            if contact.phone == phone:
                return contact
        for member in self.family_members:
            if member.phone == phone:
                return member   
        return None


    def add_family_member(self, name, new_member:FamilyMember):
        assert name == new_member.name
        self.family_members.append(new_member)
        self.save_data()

    def list_contacts(self):
        return self.contacts

    def list_family_members(self):
        return self.family_members
    
    #def register_to_ai_bus(self, ai_bus:AIBus):
    #    ai_bus.register_message_handler("contact_manager", self.process_msg)
    

    #async def process_msg(self,msg:AgentMsg):
    #    # forword message to contact    
    #    pass
