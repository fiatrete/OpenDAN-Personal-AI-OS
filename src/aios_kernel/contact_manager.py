from typing import List
import toml

class Contact:
    def __init__(self, name, phone=None, email=None, telegram=None,added_by=None, tags=[], notes=""):
        self.name = name
        self.phone = phone
        self.email = email
        self.telegram = telegram
        self.added_by = added_by
        self.tags = tags
        self.notes = notes
        self.is_family_member = False

    def to_dict(self):
        return {
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "telegram" : self.telegram,

            "added_by": self.added_by,
            "tags": self.tags,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, data):
        return Contact(data.get("name"), data.get("phone"), data.get("email"), data.get("telegram"),data.get("added_by"), data.get("tags"), data.get("notes"))

class FamilyMember(Contact):
    def __init__(self, name, relationship,phone=None, email=None,telegram=None):
        super().__init__(name, phone, email, telegram)
        self.name = name
        self.relationship = relationship  
        self.is_family_member = True

    def to_dict(self):
        result = super().to_dict()
        result["relationship"] = self.relationship
        return result

    @classmethod
    def from_dict(cls, data):
        return FamilyMember(data.get("name"),data.get("relationship"),data.get("phone"), data.get("email"),data.get("telegram"))

class ContactManager:
    _instance = None
    @classmethod
    def get_instance(cls,filename=None) -> "ContactManager":
        if cls._instance is None:
            cls._instance = ContactManager(filename)
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
