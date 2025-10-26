# document_ingestion.py

"""
Document ingestion system for PDF processing and vector storage.

Dependencies:
pip install pinecone-client python-dotenv httpx langchain-openai "unstructured[pdf]" PyMuPDF tiktoken
"""

import os
import io
import httpx
import hashlib
import asyncio
import fitz  # PyMuPDF
import tiktoken
from dotenv import load_dotenv
from pinecone import Pinecone as PineconeClient
from urllib.parse import urlparse
from typing import List, Generator
from concurrent.futures import ProcessPoolExecutor

# Langchain and Unstructured imports
from langchain_community.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from unstructured.partition.auto import partition
from unstructured.documents.elements import Element, Title, ListItem

# --- CONFIGURATION ---
load_dotenv()

# Configuration constants
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
EMBEDDING_BATCH_SIZE = 256
MIN_CHUNK_TOKENS = 100
TARGET_CHUNK_TOKENS = 350
MAX_CHUNK_TOKENS = 500
MAX_CHUNK_TOKENS_LIST = 600

# ==============================================================================
# 1. SHARED UTILITIES & MODEL INITIALIZATION
# ==============================================================================

print("Initializing OpenAI embedding model...")
EMBEDDING_MODEL = OpenAIEmbeddings(model="text-embedding-3-small", dimensions=1536)
print("OpenAI embedding model initialized.")

def _create_namespace_from_url(url: str) -> str:
    """Create a unique namespace identifier from URL."""
    parsed_url = urlparse(url.lower())
    normalized_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    return hashlib.sha256(normalized_url.encode('utf-8')).hexdigest()

def count_tokens(text: str) -> int:
    """Count tokens using the same tokenizer as the embedding models."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text, disallowed_special=()))
    except Exception:
        return len(text.split())  # Fallback to word count if tiktoken fails

# ==============================================================================
# 2. DOCUMENT PROCESSING LOGIC
# ==============================================================================

def stream_pdf_pages(url: str, document_stream: io.BytesIO) -> Generator[Element, None, None]:
    """Stream PDF pages and extract elements using unstructured."""
    try:
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
        print(f"PyMuPDF failed to process '{url}' with error: {e}. Falling back.")
        print(f"-----------------------\n")
        document_stream.seek(0)
        yield from partition(file=document_stream, strategy="fast")

def load_and_chunk_document(url: str, document_stream: io.BytesIO) -> List[Document]:
    """Load and chunk document into manageable pieces."""
    print(f"[CPU-Bound] Starting token-based chunking for document from URL: {url}")

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
        if not text:
            return

        metadata = {
            "source": url,
            "title": hierarchy_stack[-1].strip(),
            "hierarchy": " > ".join(h.strip() for h in hierarchy_stack),
            "text": text,
            "token_count": count_tokens(text)
        }

        doc = Document(page_content=text, metadata=metadata)
        chunked_documents.append(doc)

    for el in stream_pdf_pages(url, document_stream):
        if not hasattr(el, 'text') or not el.text:
            continue

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
            for sub_chunk in sub_chunks:
                create_and_save_chunk(sub_chunk)
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

    print(f"[CPU-Bound] Successfully chunked document from {url} into {len(chunked_documents)} sections.")
    return chunked_documents

# ==============================================================================
# 3. CORE INGESTION LOGIC
# ==============================================================================

async def ingest_document(pinecone_client: PineconeClient, pinecone_index_host: str, 
                         doc_url: str, executor: ProcessPoolExecutor):
    """Ingest a single document into Pinecone vector database."""
    print("\n" + "=" * 50)
    print(f"Processing document: {doc_url}")

    namespace = _create_namespace_from_url(doc_url)

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
        document_stream = io.BytesIO()

        async with httpx.AsyncClient(timeout=120.0) as client:
            print(f"Streaming download: {doc_url}")
            async with client.stream("GET", doc_url) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    document_stream.write(chunk)

        document_stream.seek(0)
        print(f"Finished streaming: {doc_url}")

        loop = asyncio.get_running_loop()
        chunked_docs = await loop.run_in_executor(
            executor, load_and_chunk_document, doc_url, document_stream
        )

        if not chunked_docs:
            print(f"No chunks were created for {doc_url}. Aborting ingestion.")
            return

        print(f"Total chunks to process: {len(chunked_docs)}. Processing in batches of {EMBEDDING_BATCH_SIZE}...")

        for i in range(0, len(chunked_docs), EMBEDDING_BATCH_SIZE):
            batch_docs = chunked_docs[i:i + EMBEDDING_BATCH_SIZE]
            batch_num = i // EMBEDDING_BATCH_SIZE + 1

            texts_to_embed = [doc.page_content for doc in batch_docs]
            print(f" - Creating embeddings for batch {batch_num} ({len(texts_to_embed)} chunks)...")

            embeddings = await loop.run_in_executor(
                None, EMBEDDING_MODEL.embed_documents, texts_to_embed
            )

            ids = [f"chunk_{i + j + 1}" for j in range(len(batch_docs))]
            metadata_to_upload = [doc.metadata for doc in batch_docs]
            vectors_to_upsert = list(zip(ids, embeddings, metadata_to_upload))

            print(f" - Uploading {len(vectors_to_upsert)} vectors for batch {batch_num}...")
            await loop.run_in_executor(
                None, lambda: pinecone_index.upsert(vectors=vectors_to_upsert, namespace=namespace)
            )

        print(f"Successfully ingested document '{doc_url}'.")

    except Exception as e:
        print(f"\n--- CRITICAL ERROR during ingestion for {doc_url} ---")
        import traceback
        traceback.print_exc()
        print("--- END ERROR ---\n")

# ==============================================================================
# 4. MAIN EXECUTION FUNCTIONS
# ==============================================================================

async def process_documents(documents_to_ingest: List[str]):
    """Process multiple documents for ingestion."""
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    pinecone_index_host = os.getenv("PINECONE_INDEX_HOST")

    if not all([pinecone_api_key, pinecone_index_host, PINECONE_INDEX_NAME]):
        print("Error: Ensure PINECONE_API_KEY, PINECONE_INDEX_HOST, and PINECONE_INDEX_NAME are set in your .env file.")
        return

    pinecone_client = PineconeClient(api_key=pinecone_api_key)

    with ProcessPoolExecutor() as executor:
        tasks = [
            ingest_document(pinecone_client, pinecone_index_host, url, executor)
            for url in documents_to_ingest
        ]
        await asyncio.gather(*tasks)

    print("\n" + "=" * 50)
    print("Ingestion process finished for all specified documents.")

def run_ingestion(documents: List[str]):
    """Main entry point for document ingestion."""
    if not documents:
        print("No documents provided for ingestion.")
        return

    print(f"Starting document ingestion script for {len(documents)} documents...")
    asyncio.run(process_documents(documents))

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    # Example usage - replace with your document URLs
    sample_documents = [
        # Add your document URLs here
    ]

    run_ingestion(sample_documents)
