from abc import ABC, abstractmethod
import random
from typing import Optional
import logging
import asyncio
import tiktoken

from asyncio import Queue

from knowledge import ObjectID
from .agent_base import AgentPrompt
from .compute_node import ComputeNode
from .compute_task import ComputeTask, ComputeTaskState, ComputeTaskResult, ComputeTaskType,ComputeTaskResultCode

logger = logging.getLogger(__name__)

# How to dispatch different computing tasks (some tasks may contain a large amount of state for correct execution)
# to suitable computing nodes, achieving a balance of speed, cost, and power consumption,
# is the CORE GOAL of the entire computing task schedule system (aios_kernel).


class ComputeKernel:
    _instance = None
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ComputeKernel()
        return cls._instance

    def __init__(self) -> None:
        self.is_start = False
        self.task_queue = Queue()
        self.is_start = False
        self.compute_nodes = {}

    def run(self, task: ComputeTask) -> None:
        # check there is compute node can support this task
        if self.is_task_support(task) is False:
            logger.error(
                f"task {task.display()} is not support by any compute node")
            return
        # add task to working_queue
        self.task_queue.put_nowait(task)

    async def start(self):
        if self.is_start is True:
            logger.warn("compute_kernel is already start")
            return

        self.is_start = True

        async def _run_task_loop():
            while True:
                task = await self.task_queue.get()
                logger.info(f"compute_kernel get task: {task.display()}")
                c_node: ComputeNode = self._schedule(task)
                if c_node:
                    await c_node.push_task(task)

            logger.warn("compute_kernel is stoped!")

        asyncio.create_task(_run_task_loop())

    def _schedule(self, task) -> ComputeNode:
        # find all the node which supports this task
        support_nodes = []
        total_weights = 0

        for node in self.compute_nodes.values():
            if node.is_support(task) is True:
                support_nodes.append({
                    "pos": total_weights,
                    "node": node
                })
                total_weights += node.weight()

        if len(support_nodes) < 1:
            logger.warning(f"task {task.display()} is not support by any compute node")
            return None
        
        # hit a random node with weight
        hit_pos = random.randint(0, total_weights - 1)
        for i in range(min(len(support_nodes) - 1, hit_pos), -1, -1):
            if support_nodes[i]["pos"] <= hit_pos:
                return support_nodes[i]["node"]

        logger.warning(
            f"task {task.display()} is not support by any compute node")
        return None

    def add_compute_node(self, node: ComputeNode):
        if self.compute_nodes.get(node.node_id) is not None:
            logger.warn(
                f"compute_node {node.display()} already in compute_kernel")
            return
        self.compute_nodes[node.node_id] = node
        logger.info(f"add compute_node {node.display()} to compute_kernel")

    def disable_compute_node(self, node_id: str):
        node = self.compute_nodes.get(node_id)
        if node is None:
            logger.warn(f"compute_node {node_id} not in compute_kernel")
            return
        node.enable = False

    def is_task_support(self, task: ComputeTask) -> bool:
        return True

    @staticmethod
    def llm_num_tokens_from_text(text:str,model:str) -> int:
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.debug("Warning: model not found. Using cl100k_base encoding.")
            encoding = tiktoken.get_encoding("cl100k_base")

        token_count = len(encoding.encode(text))
        return token_count


    # friendly interface for use:
    def llm_completion(self, prompt: AgentPrompt, resp_mode:str="text",mode_name: Optional[str] = None, max_token: int = 0,inner_functions = None):
        # craete a llm_work_task ,push on queue's end
        # then task_schedule would run this task.(might schedule some work_task to another host)
        task_req = ComputeTask()
        task_req.set_llm_params(prompt,resp_mode,mode_name, max_token,inner_functions)
        self.run(task_req)
        return task_req
    
    async def _wait_task(self,task_req:ComputeTask)->ComputeTaskResult:        
        async def check_timer():
            check_times = 0
            while True:
                if task_req.state == ComputeTaskState.DONE:
                    break

                if task_req.state == ComputeTaskState.ERROR:
                    break

                if check_times >= 120:
                    task_req.state = ComputeTaskState.ERROR
                    break

                await asyncio.sleep(0.5)
                check_times += 1

        await asyncio.create_task(check_timer())
        if task_req.result:
            return task_req.result
        else:
            time_out_result = ComputeTaskResult()
            time_out_result.result_code = ComputeTaskResultCode.TIMEOUT
            time_out_result.set_from_task(task_req)
            task_req.result = time_out_result
            return time_out_result


    async def do_llm_completion(self, prompt: AgentPrompt,resp_mode:str="text", mode_name: Optional[str] = None, max_token: int = 0, inner_functions = None) -> str:
        task_req = self.llm_completion(prompt, resp_mode,mode_name, max_token,inner_functions)
        return await self._wait_task(task_req)


    def text_embedding(self,input:str,model_name:Optional[str] = None):
        task_req = ComputeTask()
        task_req.set_text_embedding_params(input,model_name)
        self.run(task_req)
        return task_req

    async def do_text_embedding(self,input:str,model_name:Optional[str] = None) -> [float]:
        task_req = self.text_embedding(input,model_name)
        task_result = await self._wait_task(task_req)

        if task_req.state == ComputeTaskState.DONE:
            return task_result.result.get("content")
        else:
            logging.warning(f"do_text_embedding error: {task_req.error_str},input: {input}")
        return None

    def image_embedding(self,input:ObjectID,model_name:Optional[str] = None):
        task_req = ComputeTask()
        task_req.set_image_embedding_params(input,model_name)
        self.run(task_req)
        return task_req
    
    async def do_image_embedding(self,input:ObjectID,model_name:Optional[str] = None) -> [float]:
        task_req = self.image_embedding(input,model_name)
        task_result = await self._wait_task(task_req)

        if task_req.state == ComputeTaskState.DONE:
            return task_result.result.get("content")

        return None

    async def do_text_to_speech(self,
                       input:str,
                       language_code:Optional[str] = None,
                       gender: Optional[str] = None,
                       age: Optional[str] = None,
                       voice_name: Optional[str] = None,
                       tone: Optional[str] = None):
        task_req = ComputeTask()
        task_req.params["text"] = input
        task_req.params["language_code"] = language_code
        task_req.params["gender"] = gender
        task_req.params["age"] = age
        task_req.params["voice_name"] = voice_name
        task_req.params["tone"] = tone
        task_req.task_type = ComputeTaskType.TEXT_2_VOICE
        self.run(task_req)

        task_result = await self._wait_task(task_req)

        if task_req.state == ComputeTaskState.DONE:
            return task_result.result


    def text_2_image(self, prompt:str, model_name:Optional[str] = None, negative_prompt = None):
        task = ComputeTask()
        task.set_text_2_image_params(prompt,model_name, negative_prompt)
        self.run(task)
        return task

    async def do_text_2_image(self, prompt:str, model_name:Optional[str] = None, negative_prompt = None) -> ComputeTaskResult:
        task = self.text_2_image(prompt,model_name, negative_prompt)
        task = await self._wait_task(task)

        return task.result
        # if task_req.state == ComputeTaskState.DONE:
        #     return None, task_result

    def image_2_text(self, image_path: str, prompt:str, model_name:Optional[str] = None, negative_prompt = None):
        task = ComputeTask()
        task.set_image_2_text_params(image_path,prompt,model_name, negative_prompt)
        self.run(task)
        return task
    async def do_image_2_text(self, image_path: str, prompt:str, model_name:Optional[str] = None, negative_prompt = None) -> ComputeTaskResult:
        task = self.image_2_text(image_path,prompt, model_name, negative_prompt)
        task = await self._wait_task(task)
        return task.result

