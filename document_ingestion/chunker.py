from langchain_text_splitters import (RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter, PythonCodeTextSplitter)
from langchain_core.documents import Document
import re
import hashlib


def recursive_split_documents(docs: list[Document], chunk_size=1024, chunk_overlap=200) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,  # chunk size (characters)
        chunk_overlap=chunk_overlap,  # chunk overlap (characters)
        add_start_index=True,  # track index in original document
    )
    return text_splitter.split_documents(docs)

# Fixed length chunking, likely unnecessary
# def length_split_documents(docs: list[Document], chunk_size=1000, chunk_overlap=100) -> list[Document]:
#     text_splitter = CharacterTextSplitter.from_tiktoken_encoder(
#         encoding_name="cl100k_base", chunk_size=chunk_size, chunk_overlap=chunk_overlap
#     )
#     text_chunks = text_splitter.split_text(docs)
#     # TODO: turn split chunks into seperate documents
#     return []

def header_chunk_documents(docs: list[Document], recursive=False, chunk_size=1024, chunk_overlap=200) -> list[Document]:
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on)
    new_documents: list[Document] = []
    for doc in docs:
        document_splits = markdown_splitter.split_text(doc.page_content)
        if recursive:
            document_splits = recursive_split_documents(document_splits, chunk_size, chunk_overlap)
        # Preserve metadata
        for split in document_splits:
            split.metadata = doc.metadata.copy()
            split.id = stable_chunk_id(split)
        new_documents.extend(document_splits)
    return new_documents

def stable_chunk_id(doc: Document) -> str:
    """
    Create a deterministic ID so re-indexing the same chunk does not create duplicates.
    Uses only hashed page_content as a UID, so seperate documents with the exact same content are considered duplicates.
    """
    return hashlib.sha256(re.sub(r"\s+", " ", doc.page_content.lower()).strip().encode("utf-8")).hexdigest()
