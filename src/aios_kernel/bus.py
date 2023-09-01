from typing import Any
from .agent_message import AgentMsg,AgentMsgState
import asyncio
from asyncio import Queue

import logging

logger = logging.getLogger(__name__)

class AIBusHandler:
    def __init__(self,handler:Any) -> None:
        self.handler = handler
        self.working_task = None
        self.results = {}
        self.queue:Queue = Queue()

    async def handle_message(self,msg:AgentMsg) -> Any:
        if self.handler is None:
            return None
        
        return await self.handler(msg)


class AIBus:
    _instance = None
    @classmethod
    def get_default_bus(cls):
        if cls._instance is None:
            cls._instance = AIBus()
        return cls._instance

    def __init__(self) -> None:
        self.handlers = {}
        self.unhandle_handler = None
        
    async def post_message(self,target_id,msg:AgentMsg,use_unhandle=True) -> bool:
        target_id = target_id.split(".")[0]
        handler = self.handlers.get(target_id)
        if handler:
            handler.queue.put_nowait(msg)
            self.start_process(target_id)
            return True
        
        if use_unhandle:
            if self.unhandle_handler is not None:
                if await self.unhandle_handler(self,msg):
                    return await self.post_message(target_id,msg,False)
      
        logger.warn(f"post message to {msg.target} failed!,target not found")
        return False

    def resp_message(self,my_id:str,org_msg_id:str,resp:AgentMsg) -> None:
        handler = self.handlers.get(my_id)
        if handler is None:
            return None
        handler.results[org_msg_id] = resp

    async def get_message_resp(self,name:str,msg_id:str) -> AgentMsg:
        handler = self.handlers.get(name)
        if handler is None:
            return None
        
        return handler.results.get(msg_id)

    async def send_message(self,target_id:str,msg:AgentMsg) -> AgentMsg:
        target_id = target_id.split(".")[0]
        post_result = await self.post_message(target_id,msg)
        if post_result is False:
            return None
        
        handler = self.handlers.get(target_id)
        if handler is None:
            return None
                
        retry_times = 0
        while True:
            resp = handler.results.get(msg.id)
            if resp is not None:
                msg.resp_msg = resp
                msg.state = AgentMsgState.RESPONSED
                return resp
            
            await asyncio.sleep(0.2)
            retry_times += 1
            if retry_times > 100:
                msg.state = AgentMsgState.ERROR
                return None
            
        return None
    
    def register_unhandle_message_handler(self,handler:Any) -> Queue:
        self.unhandle_handler = handler

    # means sub
    def register_message_handler(self,handler_name:str,handler:Any) -> Queue:        
        handler_node =  AIBusHandler(handler) 
        self.handlers[handler_name] = handler_node
        return handler_node.queue
    
    async def process_queue(self, handler:AIBusHandler):
        while True:
            # Wait for a message
            message = await handler.queue.get()

            try:
                # Try to handle the message
                result = await handler.handle_message(message)
                handler.results[message.id] = result
            except Exception as e:
                # If an error occurs, put the message back into the queue
                logger.error(f"handle message {message.id} failed! {e}")
                #self.queues[name].put_nowait(message)
        
        return

    def start_process(self,target_name):
        handler = self.handlers.get(target_name)
        if handler is None:
            logger.error(f"handler {target_name} not found!")
            return
        
        if handler.handler is None:
            return

        if handler.working_task is not None:
            logger.warn(f"handler {target_name} is already working!")
            return
        
        handler.working_task = asyncio.create_task(self.process_queue(handler))

    

#send message to target logic:
# find target handler:
#   process_message(msg):
#       session = get_session(msg.sender,msg.target)


# history: open(sender,target,topic)