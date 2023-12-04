import os
import hashlib
import re
import tiktoken
import logging
from typing import Callable, Iterable, Optional, Tuple, List
from .chunk_store import ChunkStore
from .chunk import ChunkID, PositionFileRange, PositionType
from ..object import HashValue
from .tracker import ChunkTracker
from .chunk_list import ChunkList

def _join_docs(docs: List[str], separator: str) -> Optional[str]:
    text = separator.join(docs)
    text = text.strip()
    if text == "":
        return None
    else:
        return text

def _merge_splits(
        splits: Iterable[str],
        separator: str,
        chunk_size: int,
        chunk_overlap: int,
        length_function: Callable[[str], int]
    ) -> List[str]:
    # We now want to combine these smaller pieces into medium size
    # chunks to send to the LLM.
    separator_len = length_function(separator)

    docs = []
    current_doc: List[str] = []
    total = 0
    for d in splits:
        _len = length_function(d)
        if (
            total + _len + (separator_len if len(current_doc) > 0 else 0)
            > chunk_size
        ):
            if total > chunk_size:
                logging.warning(
                    f"Created a chunk of size {total}, "
                    f"which is longer than the specified {self._chunk_size}"
                )
            if len(current_doc) > 0:
                doc = _join_docs(current_doc, separator)
                if doc is not None:
                    docs.append(doc)
                # Keep on popping if:
                # - we have a larger chunk than in the chunk overlap
                # - or if we still have any chunks and the length is long
                while total > chunk_overlap or (
                    total + _len + (separator_len if len(current_doc) > 0 else 0)
                    > chunk_size
                    and total > 0
                ):
                    total -= length_function(current_doc[0]) + (
                        separator_len if len(current_doc) > 1 else 0
                    )
                    current_doc = current_doc[1:]
        current_doc.append(d)
        total += _len + (separator_len if len(current_doc) > 1 else 0)
    doc = _join_docs(current_doc, separator)
    if doc is not None:
        docs.append(doc)
    return docs


def _split_text_with_regex(
    text: str, separator: str, keep_separator: bool
) -> List[str]:
    # Now that we have the separator, split the text
    if separator:
        if keep_separator:
            # The parentheses in the pattern keep the delimiters in the result.
            _splits = re.split(f"({separator})", text)
            splits = [_splits[i] + _splits[i + 1] for i in range(1, len(_splits), 2)]
            if len(_splits) % 2 == 0:
                splits += _splits[-1:]
            splits = [_splits[0]] + splits
        else:
            splits = re.split(separator, text)
    else:
        splits = list(text)
    return [s for s in splits if s != ""]


def split_text(
        text: str,
        separators: List[str],
        chunk_size: int,
        chunk_overlap: int,
        length_function: Callable[[str], int]
    ) -> List[str]:

    """Split incoming text and return chunks."""
    final_chunks = []
    # Get appropriate separator to use
    separator = separators[-1]
    new_separators = []
    for i, _s in enumerate(separators):
        _separator = re.escape(_s)
        if _s == "":
            separator = _s
            break
        if re.search(_separator, text):
            separator = _s
            new_separators = separators[i + 1 :]
            break

    keep_separator = True
    _separator = re.escape(separator)
    splits = _split_text_with_regex(text, _separator, keep_separator)

    # Now go merging things, recursively splitting longer texts.
    _good_splits = []
    _separator = "" if keep_separator else separator
    for s in splits:
        if length_function(s) < chunk_size:
            _good_splits.append(s)
        else:
            if _good_splits:
                merged_text = _merge_splits(_good_splits, _separator, chunk_size, chunk_overlap, length_function)
                final_chunks.extend(merged_text)
                _good_splits = []
            if not new_separators:
                final_chunks.append(s)
            else:
                other_info = split_text(s, new_separators, chunk_size, chunk_overlap, length_function)
                final_chunks.extend(other_info)
    if _good_splits:
        merged_text = _merge_splits(_good_splits, _separator, chunk_size, chunk_overlap, length_function)
        final_chunks.extend(merged_text)
    return final_chunks

class ChunkListWriter:
    def __init__(self, chunk_store: ChunkStore, chunk_tracker: ChunkTracker):
        self.chunk_store = chunk_store
        self.chunk_tracker = chunk_tracker

    def create_chunk_list_from_file(
        self, file_path: str, chunk_size: int, restore: bool
    ) -> ChunkList:
        assert (
            chunk_size % (1024 * 1024) == 0
        ), "chunk size should be an integral multiple of 1MB"
        chunk_list = []
        hash_obj = hashlib.sha256()

        with open(file_path, "rb") as file:
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break

                chunk_len = len(chunk)
                chunk_id = ChunkID.hash_data(chunk)
                chunk_list.append(chunk_id)

                hash_obj.update(chunk)

                if restore:
                    self.chunk_tracker.add_position(
                        chunk_id, file_path, PositionType.ChunkStore
                    )
                    self.chunk_store.put_chunk(chunk_id, chunk)
                else:
                    pos = file.tell()
                    file_range = PositionFileRange(
                        file_path, pos - chunk_len, pos
                    )
                    self.chunk_tracker.add_position(
                        chunk_id, str(file_range), PositionType.FileRange
                    )

        file_hash = HashValue(hash_obj.digest())
        # print(f"calc file hash: {file_path}, {file_hash}")

        return ChunkList(chunk_list, file_hash)

    def create_chunk_list_from_text(
        self,
        text: str,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        separators: str = ["\n\n", "\n", " ", ""]
    ) -> ChunkList:
        enc = tiktoken.encoding_for_model("gpt-3.5-turbo")

        def length_function(text: str) -> int:
            return len(
                enc.encode(
                    text,
                    allowed_special=set(),
                    disallowed_special="all",
                )
            )

        text_list = split_text(text, separators, chunk_size, chunk_overlap, length_function)
        chunk_list = []
        hash_obj = hashlib.sha256()

        for text in text_list:
            chunk_bytes = text.encode("utf-8")
            hash_obj.update(chunk_bytes)

            chunk_id = ChunkID.hash_data(chunk_bytes)
            chunk_list.append(chunk_id)
            self.chunk_tracker.add_position(chunk_id, "", PositionType.ChunkStore)
            self.chunk_store.put_chunk(chunk_id, chunk_bytes)

        hash = HashValue(hash_obj.digest())
        return ChunkList(chunk_list, hash)
