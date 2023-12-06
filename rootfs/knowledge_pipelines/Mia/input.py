import copy
import os
from typing import List

import aiofiles
import chardet
import logging
import string
import docx2txt
from PyPDF2 import PdfReader

from aios import KnowledgePipelineEnvironment, ImageObjectBuilder, DocumentObjectBuilder, KnowledgeStore, RichTextObject
from aios.agent.agent_base import AgentPrompt
from aios.frame.compute_kernel import ComputeKernel
from aios.knowledge.data.writer import split_text
from aios.proto.compute_task import ComputeTaskResult, ComputeTaskResultCode
from aios.storage.storage import AIStorage
from aios.utils import video_utils, image_utils


class KnowledgeDirSource:
    def __init__(self, env: KnowledgePipelineEnvironment, config):
        self.env = env
        path = string.Template(config["path"]).substitute(myai_dir=AIStorage.get_instance().get_myai_dir())
        config["path"] = path
        self.config = config

    # @classmethod
    # def user_config_items(cls):
    #     return [("path", "local dir path")]

    def path(self):
        return self.config["path"]

    @staticmethod
    async def read_txt_file(file_path:str)->str:
        cur_encode = "utf-8"
        async with aiofiles.open(file_path,'rb') as f:
            cur_encode = chardet.detect(await f.read())['encoding']

        async with aiofiles.open(file_path,'r',encoding=cur_encode) as f:
            return await f.read()

    async def next(self):
        while True:
            journals = self.env.journal.latest_journals(1)
            from_time = 0
            if len(journals) == 1:
                latest_journal = journals[0]
                if latest_journal.is_finish():
                    yield None
                    continue
                from_time = os.path.getctime(latest_journal.get_input())
                if os.path.getmtime(self.path()) <= from_time:
                    yield (None, None)
                    continue

            file_pathes = sorted(os.listdir(self.path()), key=lambda x: os.path.getctime(os.path.join(self.path(), x)))
            for rel_path in file_pathes:
                file_path = os.path.join(self.path(), rel_path)
                timestamp = os.path.getctime(file_path)
                if timestamp <= from_time:
                    continue
                ext = os.path.splitext(file_path)[1].lower()
                if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    logging.info(f"knowledge dir source found image file {file_path}")
                    image = ImageObjectBuilder({}, {}, file_path).build(self.env.get_knowledge_store())
                    await self.env.get_knowledge_store().insert_object(image)
                    yield (image.calculate_id(), file_path)
                if ext in ['.txt']:
                    logging.info(f"knowledge dir source found text file {file_path}")
                    text = await self.read_txt_file(file_path)
                    document = DocumentObjectBuilder({}, {}, text).build(self.env.get_knowledge_store())
                    await self.env.get_knowledge_store().insert_object(document)
                    yield (document.calculate_id(), file_path)
            yield (None, None)


def init(env: KnowledgePipelineEnvironment, params: dict) -> KnowledgeDirSource:
    return KnowledgeDirSource(env, params)


async def image_to_text(images: List[str]) -> str:
    msg_prompt = AgentPrompt()
    image_prompt = "What's in this image?"
    content = [{"type": "text", "text": image_prompt}]
    content.extend([{"type": "image_url", "image_url": {"url": image_utils.to_base64(image)}} for image in images])
    msg_prompt.messages = [{"role": "user", "content": content}]

    resp: ComputeTaskResult = await (ComputeKernel.get_instance()
                                     .do_llm_completion(prompt=msg_prompt,
                                                        resp_mode="text",
                                                        mode_name="gpt-4-vision-preview",
                                                        max_token=4000,
                                                        inner_functions=None,
                                                        timeout=None))
    if resp.result_code != ComputeTaskResultCode.OK:
        raise Exception(f"image_to_text error: {resp.result_code} msg:{resp.error_str}")
    return resp.result_str


async def video_to_text(video: str) -> str:
    prompt = "These pictures are key frames extracted from the video. Please describe the content of the video based on these key frames."
    frames = video_utils.extract_frames(video, (1024, 1024))
    msg_prompt = AgentPrompt()
    content = [{"type": "text", "text": prompt}]
    content.extend([{"type": "image_url", "image_url": {"url": frame}} for frame in frames])
    msg_prompt.messages = [{"role": "user", "content": content}]
    resp: ComputeTaskResult = await (ComputeKernel.get_instance()
                                     .do_llm_completion(prompt=msg_prompt,
                                                        resp_mode="text",
                                                        mode_name="gpt-4-vision-preview",
                                                        max_token=4000,
                                                        inner_functions=None,
                                                        timeout=None))
    if resp.result_code != ComputeTaskResultCode.OK:
        raise Exception(f"video_to_text error: {resp.result_code} msg:{resp.error_str}")
    return resp.result_str


async def summary_document(text: str, separators: List[str]=["\n\n", "\n"]) -> str:
    chunks = split_text(text, separators=separators, chunk_size=4000, chunk_overlap=200, length_function=len)

    prompt = AgentPrompt()
    prompt.system_message = {"role":"system","content":"Your job is to generate a summary based on the input."}
    if len(chunks) == 1:
        prompt.append(AgentPrompt(chunks[0]))
        resp = await (ComputeKernel.get_instance()
                      .do_llm_completion(prompt=prompt,
                                         resp_mode="text",
                                         mode_name="gpt-4-1106-preview",
                                         max_token=4000,
                                         inner_functions=None,
                                         timeout=None))
        if resp.result_code != ComputeTaskResultCode.OK:
            raise Exception(f"summary_document error: {resp.result_code} msg:{resp.error_str}")
        return resp.result_str

    segments = []
    for i, chunk in enumerate(chunks):
        seg_prompt = copy.deepcopy(prompt)
        seg_prompt.append(AgentPrompt(chunk))
        resp = await (ComputeKernel.get_instance()
                      .do_llm_completion(prompt=seg_prompt,
                                         resp_mode="text",
                                         mode_name="gpt-4-1106-preview",
                                         max_token=4000,
                                         inner_functions=None,
                                         timeout=None))
        if resp.result_code != ComputeTaskResultCode.OK:
            raise Exception(f"summary_document error: {resp.result_code} msg:{resp.error_str}")
        segments.append(resp.result_str)

    segments_str = "\n".join(segments)
    prompt.append(AgentPrompt(f"Please combine the summaries of the following paragraphs into one complete summary:\n{segments_str}"))
    resp = await (ComputeKernel.get_instance()
                  .do_llm_completion(prompt=prompt,
                                     resp_mode="text",
                                     mode_name="gpt-4-1106-preview",
                                     max_token=4000,
                                     inner_functions=None,
                                     timeout=None))
    if resp.result_code != ComputeTaskResultCode.OK:
        raise Exception(f"summary_document error: {resp.result_code} msg:{resp.error_str}")
    return resp.result_str



def pdf_to_rich_text_object(pdf: str, store: KnowledgeStore) -> RichTextObject:
    base_name = os.path.basename(pdf)
    cache_path = os.path.join(AIStorage.get_instance().get_myai_dir(), "knowledge", "doc_cache", base_name)
    if not os.path.exists(cache_path):
        os.makedirs(cache_path)

    reader = PdfReader(pdf)
    rich_text = RichTextObject()
    page_texts = []
    image_count = 0
    for page in reader.pages:
        text = page.extract_text()
        page_texts.append(text)
        for image in page.images:
            image_path = os.path.join(cache_path, f"{image_count}_{image.name}")
            with open(image_path, "wb") as f:
                f.write(image.data)
            image_object = ImageObjectBuilder({}, {}, image_path).build(store)
            rich_text.add_image(image_object)

    document = DocumentObjectBuilder({}, {}, "".join(page_texts)).build(store)
    rich_text.add_document(document)

    return rich_text


def doc_to_rich_text_object(doc: str, store: KnowledgeStore) -> RichTextObject:
    base_name = os.path.basename(doc)
    cache_path = os.path.join(AIStorage.get_instance().get_myai_dir(), "knowledge", "doc_cache", base_name)
    if not os.path.exists(cache_path):
        os.makedirs(cache_path)
    text = docx2txt.process(doc, cache_path)

    rich_text = RichTextObject()
    for image in os.listdir(cache_path):
        image_path = os.path.join(cache_path, image)
        image_object = ImageObjectBuilder({}, {}, image_path).build(store)
        rich_text.add_image(image_object)

    document = DocumentObjectBuilder({}, {}, text).build(store)
    rich_text.add_document(document)

    return rich_text
