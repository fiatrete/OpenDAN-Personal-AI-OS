import logging
import requests
from typing import Optional, List
from pydantic import BaseModel
from typing import Union
from PIL import Image
import io
from .compute_task import ComputeTask, ComputeTaskState, ComputeTaskType
from .queue_compute_node import Queue_ComputeNode
from knowledge import ObjectID

logger = logging.getLogger(__name__)



class LocalSentenceTransformer_Text_ComputeNode(Queue_ComputeNode):
    # For valid pretrained models, see https://www.sbert.net/docs/pretrained_models.html
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        super().__init__()

        self.node_id = "local_sentence_transformer_text_embedding_node"
        self.model_name = model_name
        self.model = None

    def initial(self) -> bool:
        logger.info(
            f"LocalSentenceTransformer_Text_ComputeNode init, model_name: {self.model_name}"
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
            # logger.debug(f"LocalSentenceTransformer_Text_ComputeNode task: {task}")
            if task.task_type == ComputeTaskType.TEXT_EMBEDDING:
                input = task.params["input"]
                logger.debug(
                    f"LocalSentenceTransformer_Text_ComputeNode task input: {input}"
                )
                sentence_embeddings = self.model.encode(input)
                # logger.debug(f"LocalSentenceTransformer_Text_ComputeNode task sentence_embeddings: {sentence_embeddings}")
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
        return f"LocalSentenceTransformer_Text_ComputeNode: {self.node_id}, {self.model_name}"

    def get_capacity(self):
        pass

    def is_support(self, task: ComputeTask) -> bool:
        return task.task_type == ComputeTaskType.TEXT_EMBEDDING

    def is_local(self) -> bool:
        return True


class LocalSentenceTransformer_Image_ComputeNode(Queue_ComputeNode):
    # For valid pretrained models, see https://www.sbert.net/docs/pretrained_models.html
    def __init__(
        self,
        model_name: str = "clip-ViT-B-32",
        multi_model_name: str = "clip-ViT-B-32-multilingual-v1",
    ):
        super().__init__()

        self.node_id = "local_sentence_transformer_image_embedding_node"
        self.model_name = model_name
        self.multi_model_name = multi_model_name
        self.model = None
        self.multi_model = None

    def initial(self) -> bool:
        logger.info(
            f"LocalSentenceTransformer_Image_ComputeNode init, model_name: {self.model_name} {self.multi_model_name}"
        )

        assert self.model_name is not None
        assert self.multi_model_name is not None
        assert self.model is None
        assert self.multi_model is None

        try:
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.model_name)
            self.multi_model = SentenceTransformer(self.multi_model_name)
        except Exception as err:
            logger.error(f"load model {self.model} failed: {err}")
            return False

        return True

    def _load_image(self, source: Union[ObjectID, bytes]) -> Optional[Image]:
        image_data = None
        if isinstance(source, ObjectID):
            from knowledge import KnowledgeStore, ImageObject

            buf = KnowledgeStore().get_object_store().get_object(source)
            if buf is None:
                logger.error(f"load image object but not found! {source}")
                return None

            try:
                image_obj = ImageObject.decode(buf)
            except Exception as err:
                logger.error(f"decode ImageObject from buffer failed: {source}, {err}")
                return None

            file_size = image_obj.get_file_size()
            print(f"got image object: {source.to_base58()}, size: {file_size}")

            image_data = (
                KnowledgeStore()
                .get_chunk_reader()
                .read_chunk_list_to_single_bytes(image_obj.get_chunk_list())
            )

        elif isinstance(source, bytes):
            image_data = source
        else:
            logger.error(f"unsupport image source type: {type(source)}, {source}")
            return None

        try:
            img = Image.open(io.BytesIO(image_data))

            return img
        except Exception as err:
            logger.error(f"load image from buffer failed: {source}, {err}")
            return None

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
            # logger.debug(f"LocalSentenceTransformer_Text_ComputeNode task: {task}")
            if task.task_type == ComputeTaskType.TEXT_EMBEDDING:
                input = task.params["input"]
                logger.debug(
                    f"LocalSentenceTransformer_Text_ComputeNode task text input: {input}"
                )
                sentence_embeddings = self.multi_model.encode(input)
                # logger.debug(f"LocalSentenceTransformer_Text_ComputeNode task sentence_embeddings: {sentence_embeddings}")
                return {
                    "state": ComputeTaskState.DONE,
                    "content": sentence_embeddings,
                    "message": None,
                }
            elif task.task_type == ComputeTaskType.IMAGE_EMBEDDING:
                input = task.params["input"]
                logger.debug(
                    f"LocalSentenceTransformer_Image_ComputeNode task image input: {input}"
                )

                img = self._load_image(input)
                if img is None:
                    return {
                        "state": ComputeTaskState.ERROR,
                        "error": {"code": -1, "message": "load image failed"},
                    }

                sentence_embeddings = self.model.encode(img)

                # logger.debug(f"LocalSentenceTransformer_Text_ComputeNode task sentence_embeddings: {sentence_embeddings}")
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
        return f"LocalSentenceTransformer_Image_ComputeNode: {self.node_id}, {self.model_name}"

    def get_capacity(self):
        pass

    def is_support(self, task: ComputeTask) -> bool:
        return (
            task.task_type == ComputeTaskType.TEXT_EMBEDDING
            or task.task_type == ComputeTaskType.IMAGE_EMBEDDING
        )

    def is_local(self) -> bool:
        return True
