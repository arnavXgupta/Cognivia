# ingestion/common_utils.py

"""
Common utilities for the data ingestion pipeline.

This module centralizes shared functionality used across different ingestion scripts
(e.g., for PDFs and YouTube videos), including model initialization, Pinecone client
setup, token counting, and the core batch embedding and upserting logic.
"""

import os
import hashlib
import asyncio
from dotenv import load_dotenv
from pinecone import Pinecone as PineconeClient
from urllib.parse import urlparse
from typing import List, Tuple

import tiktoken
from langchain_community.docstore.document import Document
from langchain_core.embeddings import Embeddings
import pinecone

# --- CONFIGURATION ---
load_dotenv()

# Centralized configuration constants
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
PINECONE_INDEX_HOST = os.getenv("PINECONE_INDEX_HOST")
EMBEDDING_BATCH_SIZE = 256

# ==============================================================================
# 1. CLIENT & MODEL INITIALIZATION
# ==============================================================================

def initialize_clients() -> Tuple[PineconeClient, Embeddings]:
    """
    Initializes and returns the Pinecone client and the embedding model.
    This ensures that both are configured consistently across the application.
    """
    # Initialize Pinecone Client
    if not PINECONE_API_KEY:
        raise ValueError("PINECONE_API_KEY is not set in the environment variables.")
    pinecone_client = PineconeClient(api_key=PINECONE_API_KEY)
    
    # Initialize Embedding Model (Lazy loading HuggingFaceEmbeddings to avoid circular import issues)
    from langchain_community.embeddings import HuggingFaceEmbeddings
    print("Initializing local embedding model 'intfloat/e5-small-v2'...")
    embedding_model = HuggingFaceEmbeddings(
        model_name="intfloat/e5-small-v2",
        model_kwargs={'device': 'cpu'}
    )
    print("Local embedding model initialized.")
    
    return pinecone_client, embedding_model

# ==============================================================================
# 2. SHARED HELPER FUNCTIONS
# ==============================================================================

def create_namespace_from_url(url: str) -> str:
    """Creates a unique and consistent SHA-256 hash namespace from a URL."""
    parsed_url = urlparse(url.lower())
    # Using netloc + path + query ensures uniqueness for different content on the same domain
    normalized_url = f"{parsed_url.netloc}{parsed_url.path}?{parsed_url.query}"
    return hashlib.sha256(normalized_url.encode('utf-8')).hexdigest()

def count_tokens(text: str) -> int:
    """Counts tokens using the cl100k_base tokenizer."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text, disallowed_special=()))
    except Exception:
        # Fallback for any issues with the tokenizer
        return len(text.split())

# ==============================================================================
# 3. CORE ASYNCHRONOUS UPSERT LOGIC
# ==============================================================================

async def batch_embed_and_upsert(
    pinecone_index: 'pinecone.Index', # Using string type hint to avoid import at top level
    documents: List[Document],
    embedding_model: Embeddings,
    namespace: str
) -> int:
    """
    Takes a list of documents, creates embeddings in batches, and upserts them
    to a specified Pinecone namespace. This is the core I/O-heavy function.
    """
    total_docs_processed = 0
    
    print(f"Total chunks to process: {len(documents)}. Processing in batches of {EMBEDDING_BATCH_SIZE}...")
    
    for i in range(0, len(documents), EMBEDDING_BATCH_SIZE):
        batch_docs = documents[i:i + EMBEDDING_BATCH_SIZE]
        batch_num = i // EMBEDDING_BATCH_SIZE + 1
        
        texts_to_embed = [doc.page_content for doc in batch_docs]
        print(f" - Creating embeddings for batch {batch_num} ({len(texts_to_embed)} chunks)...")

        loop = asyncio.get_running_loop()
        # Run embedding creation in a thread pool executor to not block the event loop
        embeddings = await loop.run_in_executor(
            None, embedding_model.embed_documents, texts_to_embed
        )

        ids = [f"{namespace}_chunk_{i + j}" for j in range(len(batch_docs))]
        metadata_to_upload = [doc.metadata for doc in batch_docs]
        vectors_to_upsert = list(zip(ids, embeddings, metadata_to_upload))

        print(f" - Uploading {len(vectors_to_upsert)} vectors for batch {batch_num}...")
        # Run the synchronous Pinecone upsert call in an executor
        await loop.run_in_executor(
            None, lambda: pinecone_index.upsert(vectors=vectors_to_upsert, namespace=namespace)
        )
        total_docs_processed += len(batch_docs)

    return total_docs_processed
