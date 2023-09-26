import logging
import requests
from typing import Optional, List
from pydantic import BaseModel

from .compute_task import ComputeTask, ComputeTaskState, ComputeTaskType
from .queue_compute_node import Queue_ComputeNode

logger = logging.getLogger(__name__)

"""
This is a custom implementation, it should be redesigned.
"""


class LocalSentenceTransformer_ComputeNode(Queue_ComputeNode):
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        super().__init__()

        self.node_id = "local_sentence_transformer_node"
        self.model_name = model_name
        self.model = None

    def initial(self) -> bool:
        logger.info(
            f"LocalSentenceTransformer_ComputeNode init, model_name: {self.model_name}"
        )
        
        assert self.model_name is not None
        assert self.model is None
        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.model)
        except Exception as err:
            logger.error(f"load model {self.model} failed: {err}")
            return False
        
        return True
    
    async def execute_task(
        self, task: ComputeTask
    ) -> {
        "task_type": str,
        "content": str,
        "message": str,
        "state": ComputeTaskState,
        "error": {
            "code": int,
            "message": str,
        },
    }:
        try:
            # logger.debug(f"LocalSentenceTransformer_ComputeNode task: {task}")
            if task.task_type == ComputeTaskType.TEXT_EMBEDDING:
                input = task.params["input"]
                logger.debug(
                    f"LocalSentenceTransformer_ComputeNode task input: {input}"
                )
                sentence_embeddings = self.model.encode(input)
                # logger.debug(f"LocalSentenceTransformer_ComputeNode task sentence_embeddings: {sentence_embeddings}")
                return {
                    "state": ComputeTaskState.DONE,
                    "content": sentence_embeddings,
                    "message": None,
                }
            else:
                return {
                    "state": ComputeTaskState.ERROR,
                    "error": {"code": -1, "message": "unsupport embedding task type"},
                }
        except Exception as err:
            import traceback

            logger.error(f"{traceback.format_exc()}, error: {err}")

            return {
                "state": ComputeTaskState.ERROR,
                "error": {"code": -1, "message": "unknown exception: " + str(err)},
            }

    def display(self) -> str:
        return (
            f"LocalSentenceTransformer_ComputeNode: {self.node_id}, {self.model_name}"
        )

    def get_capacity(self):
        pass

    def is_support(self, task: ComputeTask) -> bool:
        return task.task_type == ComputeTaskType.TEXT_EMBEDDING and (
            not task.params["model_name"] or task.params["model_name"] == "all-MiniLM-L6-v2"
        )

    def is_local(self) -> bool:
        return True
