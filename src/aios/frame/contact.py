from typing import List
import logging
from datetime import datetime

from ..proto.agent_msg import AgentMsg
from .tunnel import AgentTunnel


logger = logging.getLogger(__name__)    
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
        self.active_tunnels = {}

    def to_dict(self):
        return {
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "telegram" : self.telegram,

            "added_by": self.added_by,
            "tags": self.tags,
            "notes": self.notes,
            "now" : datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    async def _process_msg(self,msg:AgentMsg):
        tunnel : AgentTunnel = self.get_active_tunnel(msg.sender)
        if tunnel is not None:
            await tunnel.post_message(msg)
            return None
        else:
            tunnel = await self.create_default_tunnel(msg.sender)
            if tunnel is not None:
                self.active_tunnels[msg.sender] = tunnel
                await tunnel.post_message(msg)
                return None
        
        
        logger.warn(f"contact {self.name} cann't get tunnel,post message failed!")

    def get_active_tunnel(self,agent_id) -> AgentTunnel:
        tunnel = self.active_tunnels.get(agent_id)
        return tunnel
    
    def set_active_tunnel(self,agent_id,tunnel:AgentTunnel):
        self.active_tunnels[agent_id] = tunnel
    
    async def create_default_tunnel(self,agent_id:str) -> AgentTunnel:
        from .email_tunnel import EmailTunnel

        result_tunnels = AgentTunnel.get_tunnel_by_agentid(agent_id)
        for tunnel in result_tunnels:
            if isinstance(tunnel,EmailTunnel):
                return tunnel
                    
        return None

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
