# # pdf_ingestion.py

# import os
# import io
# import hashlib
# import asyncio
# import fitz  # PyMuPDF
# import tiktoken
# from dotenv import load_dotenv
# from pinecone import Pinecone as PineconeClient
# from typing import List, Generator
# from concurrent.futures import ProcessPoolExecutor

# # Langchain and Unstructured imports
# from langchain_community.docstore.document import Document
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from unstructured.partition.auto import partition
# from unstructured.documents.elements import Element, Title, ListItem
# # ADD THIS
# from .common_utils import (
#     initialize_clients,
#     create_namespace_from_url, # We'll adapt this for filenames
#     count_tokens,
#     batch_embed_and_upsert
# )

# # --- CONFIGURATION ---
# load_dotenv()

# # Configuration constants
# PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
# # EMBEDDING_BATCH_SIZE = 256
# EMBEDDING_BATCH_SIZE = 32
# MIN_CHUNK_TOKENS = 100
# # TARGET_CHUNK_TOKENS = 350
# # MAX_CHUNK_TOKENS = 500
# # MAX_CHUNK_TOKENS_LIST = 600
# TARGET_CHUNK_TOKENS = 250
# MAX_CHUNK_TOKENS = 350
# MAX_CHUNK_TOKENS_LIST = 400


# def count_tokens(text: str) -> int:
#     """Count tokens using the same tokenizer as the embedding models."""
#     try:
#         encoding = tiktoken.get_encoding("cl100k_base")
#         return len(encoding.encode(text, disallowed_special=()))
#     except Exception:
#         return len(text.split())  # Fallback to word count if tiktoken fails

# # ==============================================================================
# # 2. DOCUMENT PROCESSING LOGIC
# # ==============================================================================

# def stream_pdf_pages_from_file(filename: str, file_content: bytes) -> Generator[Element, None, None]:
#     """Stream PDF pages from file content and extract elements using unstructured."""
#     try:
#         document_stream = io.BytesIO(file_content)
#         doc = fitz.open(stream=document_stream, filetype="pdf")

#         for i, page in enumerate(doc):
#             new_doc = fitz.open()
#             new_doc.insert_pdf(doc, from_page=i, to_page=i)
#             page_stream = io.BytesIO(new_doc.tobytes())
#             new_doc.close()
#             yield from partition(file=page_stream, strategy="fast")

#         doc.close()
#     except Exception as e:
#         print(f"\n--- PyMuPDF Warning ---")
#         print(f"PyMuPDF failed to process '{filename}' with error: {e}. Falling back.")
#         print(f"-----------------------\n")

#         document_stream = io.BytesIO(file_content)
#         document_stream.seek(0)
#         yield from partition(file=document_stream, strategy="fast")

# def load_and_chunk_document_from_file(filename: str, file_content: bytes) -> List[Document]:
#     """Load and chunk document from file content into manageable pieces."""
#     print(f"[CPU-Bound] Starting token-based chunking for document: {filename}")

#     chunked_documents = []
#     current_chunk_text = ""
#     hierarchy_stack = ["Introduction"]
#     current_content_type = 'narrative'

#     fallback_splitter = RecursiveCharacterTextSplitter(
#         chunk_size=MAX_CHUNK_TOKENS,
#         chunk_overlap=int(MAX_CHUNK_TOKENS * 0.1),
#         length_function=count_tokens
#     )

#     def create_and_save_chunk(text: str):
#         nonlocal chunked_documents
#         text = text.strip()
#         if not text:
#             return

#         metadata = {
#             "source": filename,
#             "title": hierarchy_stack[-1].strip(),
#             "hierarchy": " > ".join(h.strip() for h in hierarchy_stack),
#             "text": text,
#             "token_count": count_tokens(text)
#         }

#         doc = Document(page_content=text, metadata=metadata)
#         chunked_documents.append(doc)

#     for el in stream_pdf_pages_from_file(filename, file_content):
#         if not hasattr(el, 'text') or not el.text:
#             continue

#         element_text = el.text.strip()
#         element_token_count = count_tokens(element_text)
#         element_type = type(el)

#         if element_type is Title:
#             if count_tokens(current_chunk_text) >= MIN_CHUNK_TOKENS:
#                 create_and_save_chunk(current_chunk_text)
#                 current_chunk_text = ""
#             hierarchy_stack.append(element_text)
#             current_content_type = 'narrative'
#             continue

#         if element_token_count > MAX_CHUNK_TOKENS:
#             if count_tokens(current_chunk_text) > 0:
#                 create_and_save_chunk(current_chunk_text)
#                 current_chunk_text = ""

#             sub_chunks = fallback_splitter.split_text(element_text)
#             for sub_chunk in sub_chunks:
#                 create_and_save_chunk(sub_chunk)
#             continue

#         new_content_type = 'list' if element_type is ListItem else 'narrative'
#         split_before_adding = False

#         if current_content_type != new_content_type and count_tokens(current_chunk_text) > 0:
#             split_before_adding = True
#         elif current_content_type == 'narrative' and count_tokens(current_chunk_text) >= TARGET_CHUNK_TOKENS:
#             split_before_adding = True
#         elif current_content_type == 'list' and count_tokens(current_chunk_text) >= MAX_CHUNK_TOKENS_LIST:
#             split_before_adding = True

#         if split_before_adding:
#             create_and_save_chunk(current_chunk_text)
#             current_chunk_text = ""

#         current_chunk_text += f"\n\n{element_text}"
#         current_content_type = new_content_type

#     if current_chunk_text.strip():
#         create_and_save_chunk(current_chunk_text)

#     print(f"[CPU-Bound] Successfully chunked document {filename} into {len(chunked_documents)} sections.")
#     return chunked_documents

# # ==============================================================================
# # 3. CORE INGESTION LOGIC
# # ==============================================================================

# async def ingest_document_from_file(pinecone_client: PineconeClient, pinecone_index_host: str,
#                                    filename: str, file_content: bytes, executor: ProcessPoolExecutor):
#     """Ingest a single document from file content into Pinecone vector database."""
#     print("\n" + "=" * 50)
#     print(f"Processing document: {filename}")

#     namespace = _create_namespace_from_filename(filename)

#     try:
#         pinecone_index = pinecone_client.Index(host=pinecone_index_host)
#         stats = pinecone_index.describe_index_stats()

#         if namespace in stats.namespaces and stats.namespaces[namespace].vector_count > 0:
#             print(f"Document already exists in Pinecone namespace '{namespace}'. Skipping.")
#             return
#     except Exception as e:
#         print(f"Could not connect to Pinecone index: {e}")
#         return

#     print(f"Starting new ingestion into namespace '{namespace}'...")

#     try:
#         loop = asyncio.get_running_loop()

#         chunked_docs = await loop.run_in_executor(
#             executor, load_and_chunk_document_from_file, filename, file_content
#         )

#         if not chunked_docs:
#             print(f"No chunks were created for {filename}. Aborting ingestion.")
#             return

#         print(f"Total chunks to process: {len(chunked_docs)}. Processing in batches of {EMBEDDING_BATCH_SIZE}...")

#         print(f"Successfully ingested document '{filename}'.")

#     except Exception as e:
#         print(f"\n--- CRITICAL ERROR during ingestion for {filename} ---")
#         import traceback
#         traceback.print_exc()
#         print("--- END ERROR ---\n")

# # ==============================================================================
# # 4. MAIN EXECUTION FUNCTIONS
# # ==============================================================================

# async def process_uploaded_documents(uploaded_files: List[tuple]):
#     """Process multiple uploaded documents for ingestion.

#     Args:
#         uploaded_files: List of tuples containing (filename, file_content_bytes)
#     """
#     pinecone_api_key = os.getenv("PINECONE_API_KEY")
#     pinecone_index_host = os.getenv("PINECONE_INDEX_HOST")

#     if not all([pinecone_api_key, pinecone_index_host, PINECONE_INDEX_NAME]):
#         print("Error: Ensure PINECONE_API_KEY, PINECONE_INDEX_HOST, and PINECONE_INDEX_NAME are set in your .env file.")
#         return


#     with ProcessPoolExecutor() as executor:
#         tasks = [
#             ingest_document_from_file(pinecone_client, pinecone_index_host, filename, file_content, executor)
#             for filename, file_content in uploaded_files
#         ]

#         await asyncio.gather(*tasks)

#     print("\n" + "=" * 50)
#     print("Ingestion process finished for all uploaded documents.")

# def run_ingestion_from_uploads(uploaded_files: List[tuple]):
#     """Main entry point for uploaded document ingestion.

#     Args:
#         uploaded_files: List of tuples containing (filename, file_content_bytes)
#     """
#     if not uploaded_files:
#         print("No files provided for ingestion.")
#         return

#     print(f"Starting document ingestion script for {len(uploaded_files)} uploaded files...")
#     asyncio.run(process_uploaded_documents(uploaded_files))


# without common_util file addition



# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================
# ==============================================================================





# pdf_ingestion.py

"""
Document ingestion system for PDF processing and vector storage.
This script is refactored to use a common utility module for shared logic.

It is responsible ONLY for parsing and chunking PDF files.
"""

import os
import io
import asyncio
import fitz  # PyMuPDF
from typing import List, Generator
from concurrent.futures import ProcessPoolExecutor

# Langchain and Unstructured imports
from langchain_community.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from unstructured.partition.auto import partition
from unstructured.documents.elements import Element, Title, ListItem
import pinecone

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
# Import shared logic from the common utility module
from ai.ingestion.common_utils import (
    initialize_clients,
    create_namespace_from_url, # We will use this utility for consistency
    count_tokens,
    batch_embed_and_upsert
)

# --- PDF-SPECIFIC CONFIGURATION ---
# These constants are specific to how we want to chunk PDF files.
MIN_CHUNK_TOKENS = 100
TARGET_CHUNK_TOKENS = 250
MAX_CHUNK_TOKENS = 350
MAX_CHUNK_TOKENS_LIST = 400

# ==============================================================================
# 1. PDF-SPECIFIC PROCESSING LOGIC
# (This section is unique to this file and remains unchanged)
# ==============================================================================

def stream_pdf_pages_from_file(filename: str, file_content: bytes) -> Generator[Element, None, None]:
    """Stream PDF pages from file content and extract elements using unstructured."""
    try:
        document_stream = io.BytesIO(file_content)
        doc = fitz.open(stream=document_stream, filetype="pdf")

        for i, page in enumerate(doc):
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=i, to_page=i)
            page_stream = io.BytesIO(new_doc.tobytes())
            new_doc.close()
            yield from partition(file=page_stream, strategy="fast")

        doc.close()
    except Exception as e:
        print(f"\n--- PyMuPDF Warning ---")
        print(f"PyMuPDF failed to process '{filename}' with error: {e}. Falling back.")
        print(f"-----------------------\n")
        document_stream = io.BytesIO(file_content)
        document_stream.seek(0)
        yield from partition(file=document_stream, strategy="fast")

def load_and_chunk_document_from_file(filename: str, file_content: bytes) -> List[Document]:
    """Load and chunk document from file content into manageable pieces."""
    print(f"[CPU-Bound] Starting token-based chunking for document: {filename}")
    chunked_documents = []
    current_chunk_text = ""
    hierarchy_stack = ["Introduction"]
    current_content_type = 'narrative'

    fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=MAX_CHUNK_TOKENS,
        chunk_overlap=int(MAX_CHUNK_TOKENS * 0.1),
        length_function=count_tokens
    )

    def create_and_save_chunk(text: str):
        nonlocal chunked_documents
        text = text.strip()
        if not text: return

        metadata = {
            "source": filename,
            "title": hierarchy_stack[-1].strip(),
            "hierarchy": " > ".join(h.strip() for h in hierarchy_stack),
            "text": text,
            "token_count": count_tokens(text)
        }
        doc = Document(page_content=text, metadata=metadata)
        chunked_documents.append(doc)

    for el in stream_pdf_pages_from_file(filename, file_content):
        if not hasattr(el, 'text') or not el.text: continue
        element_text = el.text.strip()
        element_token_count = count_tokens(element_text)
        element_type = type(el)

        if element_type is Title:
            if count_tokens(current_chunk_text) >= MIN_CHUNK_TOKENS:
                create_and_save_chunk(current_chunk_text)
                current_chunk_text = ""
            hierarchy_stack.append(element_text)
            current_content_type = 'narrative'
            continue

        if element_token_count > MAX_CHUNK_TOKENS:
            if count_tokens(current_chunk_text) > 0:
                create_and_save_chunk(current_chunk_text)
                current_chunk_text = ""
            sub_chunks = fallback_splitter.split_text(element_text)
            for sub_chunk in sub_chunks: create_and_save_chunk(sub_chunk)
            continue

        new_content_type = 'list' if element_type is ListItem else 'narrative'
        split_before_adding = False
        if current_content_type != new_content_type and count_tokens(current_chunk_text) > 0:
            split_before_adding = True
        elif current_content_type == 'narrative' and count_tokens(current_chunk_text) >= TARGET_CHUNK_TOKENS:
            split_before_adding = True
        elif current_content_type == 'list' and count_tokens(current_chunk_text) >= MAX_CHUNK_TOKENS_LIST:
            split_before_adding = True

        if split_before_adding:
            create_and_save_chunk(current_chunk_text)
            current_chunk_text = ""
        current_chunk_text += f"\n\n{element_text}"
        current_content_type = new_content_type

    if current_chunk_text.strip():
        create_and_save_chunk(current_chunk_text)

    print(f"[CPU-Bound] Successfully chunked document {filename} into {len(chunked_documents)} sections.")
    return chunked_documents

# ==============================================================================
# 2. CORE INGESTION & ORCHESTRATION LOGIC
# ==============================================================================

async def ingest_document_from_file(
    pinecone_client: 'pinecone.Pinecone',
    pinecone_index_host: str,
    embedding_model: 'langchain_community.embeddings.base.Embeddings',
    filename: str,
    file_content: bytes,
    executor: ProcessPoolExecutor
):
    """Orchestrates the ingestion of a single document from file content."""
    print("\n" + "=" * 50)
    print(f"Processing document: {filename}")
    
    # Using a fake URL structure so the common utility can create a consistent hash
    namespace = create_namespace_from_url(f"file://{filename}")

    try:
        pinecone_index = pinecone_client.Index(host=pinecone_index_host)
        stats = pinecone_index.describe_index_stats()
        if namespace in stats.namespaces and stats.namespaces[namespace].vector_count > 0:
            print(f"Document already exists in Pinecone namespace '{namespace}'. Skipping.")
            return
    except Exception as e:
        print(f"Could not connect to Pinecone index: {e}")
        return

    print(f"Starting new ingestion into namespace '{namespace}'...")
    try:
        loop = asyncio.get_running_loop()
        chunked_docs = await loop.run_in_executor(
            executor, load_and_chunk_document_from_file, filename, file_content
        )

        if not chunked_docs:
            print(f"No chunks were created for {filename}. Aborting ingestion.")
            return
        
        # The entire batching/embedding/upserting loop is now handled by this single function call
        await batch_embed_and_upsert(
            pinecone_index, chunked_docs, embedding_model, namespace
        )

        print(f"Successfully ingested document '{filename}'.")
    except Exception as e:
        print(f"\n--- CRITICAL ERROR during ingestion for {filename} ---")
        import traceback
        traceback.print_exc()
        print("--- END ERROR ---\n")

async def process_uploaded_documents(uploaded_files: List[tuple]):
    """Main async function to process multiple uploaded documents."""
    try:
        # Initialize clients once using the common utility function
        pinecone_client, embedding_model = initialize_clients()
        pinecone_index_host = os.getenv("PINECONE_INDEX_HOST")
        if not pinecone_index_host:
             raise ValueError("PINECONE_INDEX_HOST is not set in environment variables.")
    except Exception as e:
        print(f"Error during initialization: {e}")
        return

    with ProcessPoolExecutor() as executor:
        tasks = [
            ingest_document_from_file(
                pinecone_client, pinecone_index_host, embedding_model,
                filename, file_content, executor
            )
            for filename, file_content in uploaded_files
        ]
        await asyncio.gather(*tasks)

    print("\n" + "=" * 50)
    print("Ingestion process finished for all uploaded documents.")

def run_ingestion_from_uploads(uploaded_files: List[tuple]):
    """Main entry point for uploaded document ingestion."""
    if not uploaded_files:
        print("No files provided for ingestion.")
        return
    print(f"Starting document ingestion script for {len(uploaded_files)} uploaded files...")
    asyncio.run(process_uploaded_documents(uploaded_files))