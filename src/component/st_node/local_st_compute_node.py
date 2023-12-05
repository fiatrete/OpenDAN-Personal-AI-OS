import logging
import requests
from typing import Optional, List
from pydantic import BaseModel
from typing import Union
from PIL import Image
import io

from aios import ComputeTask, ComputeTaskResult, ComputeTaskState, ComputeTaskType,ComputeTaskResultCode,ComputeNode,AIStorage,UserConfig,ObjectID,Queue_ComputeNode

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

            self.model = SentenceTransformer(self.model_name)
        except Exception as err:
            logger.error(f"load model {self.model} failed: {err}")
            return False
        self.start()
        return True

    async def execute_task(self, task: ComputeTask) :
        result = ComputeTaskResult()
        result.result_code = ComputeTaskResultCode.ERROR
        result.set_from_task(task)
        result.worker_id = self.node_id
        try:
            # logger.debug(f"LocalSentenceTransformer_Text_ComputeNode task: {task}")
            if task.task_type == ComputeTaskType.TEXT_EMBEDDING:
                input = task.params["input"]
                logger.debug(
                    f"LocalSentenceTransformer_Text_ComputeNode task input: {input}"
                )
                sentence_embeddings = self.model.encode(input, show_progress_bar=False).tolist()
                # logger.debug(f"LocalSentenceTransformer_Text_ComputeNode task sentence_embeddings: {sentence_embeddings}")
                result.result_code = ComputeTaskResultCode.OK
                result.result["content"] = sentence_embeddings

            else:
                result.error_str = f"unsupport embedding task type: {task.task_type}"
        except Exception as err:
            import traceback

            logger.error(f"{traceback.format_exc()}, error: {err}")
            result.error_str = f"{traceback.format_exc()}, error: {err}"

        return result


    def display(self) -> str:
        return f"LocalSentenceTransformer_Text_ComputeNode: {self.node_id}, {self.model_name}"

    def get_capacity(self):
        pass

    def is_support(self, task: ComputeTask) -> bool:
        return task.task_type == ComputeTaskType.TEXT_EMBEDDING and task.params["model_name"] == "all-MiniLM-L6-v2"

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
        self.start()
        return True

    def _load_image(self, source: Union[ObjectID, bytes]) -> Optional[Image]:
        image_data = None
        if isinstance(source, ObjectID):
            from aios import KnowledgeStore, ImageObject

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
            # print(f"got image object: {source.to_base58()}, size: {file_size}")

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
    ) -> ComputeTaskResult:
        result = ComputeTaskResult()
        result.result_code = ComputeTaskResultCode.ERROR
        result.set_from_task(task)
        result.worker_id = self.node_id
        try:
            # logger.debug(f"LocalSentenceTransformer_Text_ComputeNode task: {task}")
            if task.task_type == ComputeTaskType.TEXT_EMBEDDING:
                input = task.params["input"]
                logger.debug(
                    f"LocalSentenceTransformer_Text_ComputeNode task text input: {input}"
                )
                sentence_embeddings = self.multi_model.encode(input, show_progress_bar=False).tolist()
                # logger.debug(f"LocalSentenceTransformer_Text_ComputeNode task sentence_embeddings: {sentence_embeddings}")
                result.result_code = ComputeTaskResultCode.OK
                result.result["content"] = sentence_embeddings

            elif task.task_type == ComputeTaskType.IMAGE_EMBEDDING:
                input = task.params["input"]
                logger.debug(
                    f"LocalSentenceTransformer_Image_ComputeNode task image input: {input}"
                )

                img = self._load_image(input)
                if img is None:
                    result.error_str = f"load image failed: {input}"
                    return result   

                sentence_embeddings = self.model.encode(img, show_progress_bar=False).tolist()
                result.result_code = ComputeTaskResultCode.OK
                result.result["content"] = sentence_embeddings
            else:
                result.error_str = f"unsupport embedding task type: {task.task_type}"
        except Exception as err:
            import traceback

            logger.error(f"{traceback.format_exc()}, error: {err}")
            result.error_str = f"{traceback.format_exc()}, error: {err}"
 
        
        return result

    def display(self) -> str:
        return f"LocalSentenceTransformer_Image_ComputeNode: {self.node_id}, {self.model_name}"

    def get_capacity(self):
        pass

    def is_support(self, task: ComputeTask) -> bool:
        return (
            (task.task_type == ComputeTaskType.TEXT_EMBEDDING and task.params["model_name"] == "clip-ViT-B-32")
            or task.task_type == ComputeTaskType.IMAGE_EMBEDDING
        )

    def is_local(self) -> bool:
        return True
