import unittest
import toml
import os
import sys

directory = os.path.dirname(__file__)
sys.path.append(directory + '/../src')
from aios_kernel import ContactManager, Contact, FamilyMember

class TestContactManager(unittest.TestCase):

    def setUp(self):
        self.manager = ContactManager(filename="test_contacts.toml")
        self.manager.load_data()

    def tearDown(self):
        if os.path.exists("test_contacts.toml"):
            os.remove("test_contacts.toml")

    def test_add_family_member(self):
        new_member = FamilyMember("Alice", "123-456-7890", "sdfsd","alice@example.com")
        self.manager.add_family_member("Alice", new_member)
        members = self.manager.list_family_members()
        self.assertEqual(len(members), 1)
        self.assertEqual(members[0].name, "Alice")

    def test_add_contact(self):
        new_contact = Contact("Bob", "987-654-3210", "bob@example.com", "32323","Alice", ["Friend"], "Bob is Alice's friend.")
        self.manager.add_contact("Bob", new_contact)
        contacts = self.manager.list_contacts()
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0].name, "Bob")
        self.assertEqual(contacts[0].added_by, "Alice")

    def test_remove_contact(self):
        new_contact = Contact("Bob", "987-654-3210", "bob@example.com", "32323","Alice", ["Friend"], "Bob is Alice's friend.")
        self.manager.add_contact("Bob", new_contact)
        self.manager.remove_contact("Bob")
        contacts = self.manager.list_contacts()
        self.assertEqual(len(contacts), 0)

    def test_find_contact_by_name(self):
        new_contact = Contact("Bob", "987-654-3210", "bob@example.com", "32323","Alice", ["Friend"], "Bob is Alice's friend.")
        self.manager.add_contact("Bob", new_contact)
        contact = self.manager.find_contact_by_name("Bob")
        self.assertIsNotNone(contact)
        self.assertEqual(contact.name, "Bob")

    def test_find_contact_by_email(self):
        new_contact = Contact("Bob", "987-654-3210", "bob@example.com", "32323","Alice", ["Friend"], "Bob is Alice's friend.")
        self.manager.add_contact("Bob", new_contact)
        contact = self.manager.find_contact_by_email("bob@example.com")
        self.assertIsNotNone(contact)
        self.assertEqual(contact.email, "bob@example.com")

    def test_find_contact_by_phone(self):
        new_contact = Contact("Bob", "987-654-3210", "bob@example.com", "32323","Alice", ["Friend"], "Bob is Alice's friend.")
        self.manager.add_contact("Bob", new_contact)
        contact = self.manager.find_contact_by_phone("987-654-3210")
        self.assertIsNotNone(contact)
        self.assertEqual(contact.phone, "987-654-3210")

if __name__ == '__main__':
    unittest.main()
