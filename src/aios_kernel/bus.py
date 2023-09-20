from typing import Coroutine,Dict,Any
from .agent_message import AgentMsg,AgentMsgStatus
import asyncio
from asyncio import Queue

import logging

logger = logging.getLogger(__name__)

class AIBusHandler:
    def __init__(self,handler:Coroutine,owner_bus,enable_defualt_proc=True) -> None:
        self.handler = handler
        self.working_task = None
        self.results = {} # recv resps
        self.queue:Queue = Queue()
        self.enable_defualt_proc = enable_defualt_proc
        self.owner_bus = owner_bus

    async def handle_message(self,msg:AgentMsg) -> Any:
        if self.handler is None:
            return None
        
        resp_msg = await self.handler(msg)
        if self.enable_defualt_proc:
            if resp_msg is not None:
                await self.owner_bus.post_message(resp_msg,False)

        return resp_msg
            
class AIBus:
    _instance = None
    @classmethod
    def get_default_bus(cls):
        if cls._instance is None:
            cls._instance = AIBus()
        return cls._instance

    def __init__(self) -> None:
        self.handlers:Dict[AIBusHandler] = {}
        self.unhandle_handler:Coroutine = None


    async def post_message(self,msg:AgentMsg,use_unhandle=True) -> bool:
        target_id = msg.target.split(".")[0]

        handler = self.handlers.get(target_id)
        if handler:
            if msg.rely_msg_id is not None:
                handler.results[msg.rely_msg_id] = msg
                return None
            
            handler.queue.put_nowait(msg)
            self.start_process(target_id)
            return True
        
        if use_unhandle:
            if self.unhandle_handler is not None:
                if await self.unhandle_handler(self,msg):
                    return await self.post_message(msg,False)
      
        logger.warn(f"post message to {msg.target} failed!,target not found")
        return False

    async def resp_message(self,org_msg_id:str,resp:AgentMsg) -> None:
        assert resp.rely_msg_id == org_msg_id
        return await self.post_message(resp)

    async def send_message(self,msg:AgentMsg) -> AgentMsg:
        sender_id = msg.sender.split(".")[0]
        sender_handler = self.handlers.get(sender_id) # sender already register on bus
        if sender_handler is None:
            logger.warn(f"sender {sender_id} not register on AI_BUS!")
            return None
        
        post_result = await self.post_message(msg)
        if post_result is False:
            return None

        retry_times = 0
        while True:
            resp = sender_handler.results.get(msg.msg_id)
            if resp is not None:
                msg.resp_msg = resp
                msg.status = AgentMsgStatus.RESPONSED
                del sender_handler.results[msg.msg_id]
                return resp
            
            await asyncio.sleep(0.2)
            retry_times += 1
            if retry_times > 5*120: # default timeout is 120 sec
                msg.status = AgentMsgStatus.ERROR
                return None
            
        return None
    
    def register_unhandle_message_handler(self,handler:Any) -> Queue:
        self.unhandle_handler = handler

    # means sub
    def register_message_handler(self,handler_name:str,handler:Any) -> Queue:        
        handler_node =  AIBusHandler(handler,self) 
        self.handlers[handler_name] = handler_node
        return handler_node.queue
    
    async def process_queue(self, handler:AIBusHandler):
        while True:
            # Wait for a message
            message = await handler.queue.get()

            #try:
                # Try to handle the message
            await handler.handle_message(message)
            #except Exception as e:
                # If an error occurs, put the message back into the queue
            #    logger.error(f"handle message {message.msg_id} failed! {e}")
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