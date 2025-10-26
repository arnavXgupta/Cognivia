# # ingest_youtube.py

# """
# YouTube transcript ingestion system for video processing and vector storage.

# This script fetches transcripts from YouTube videos, chunks them based on token count,
# creates embeddings using a local model, and upserts them into a Pinecone index.

# Dependencies:
# pip install pinecone-client python-dotenv langchain-community youtube-transcript-api tiktoken sentence-transformers
# """

# import os
# import hashlib
# import asyncio
# from dotenv import load_dotenv
# from pinecone import Pinecone as PineconeClient
# from urllib.parse import urlparse
# from typing import List
# from concurrent.futures import ProcessPoolExecutor

# # Langchain imports
# from langchain_community.docstore.document import Document
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_community.embeddings import HuggingFaceEmbeddings
# from langchain_community.document_loaders import YoutubeLoader

# import tiktoken

# # --- CONFIGURATION ---
# load_dotenv()

# # Pinecone and model configuration constants
# PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
# # IMPORTANT: The dimension of this index must match the embedding model's output (384 for e5-small-v2)
# PINECONE_INDEX_HOST = os.getenv("PINECONE_INDEX_HOST")
# EMBEDDING_BATCH_SIZE = 256
# CHUNK_SIZE_TOKENS = 400
# CHUNK_OVERLAP_TOKENS = 40

# # ==============================================================================
# # 1. SHARED UTILITIES & MODEL INITIALIZATION
# # ==============================================================================

# print("Initializing local embedding model 'intfloat/e5-small-v2'...")
# # Using a local model for cost-effective development.
# # The 'device':'cpu' part is important if you don't have a GPU setup.
# EMBEDDING_MODEL = HuggingFaceEmbeddings(
#     model_name="intfloat/e5-small-v2",
#     model_kwargs={'device': 'cpu'}
# )
# print("Local embedding model initialized.")

# def _create_namespace_from_url(url: str) -> str:
#     """Create a unique and consistent namespace identifier from a URL."""
#     # Normalizing the URL to ensure consistency (e.g., http vs https, www vs non-www)
#     parsed_url = urlparse(url.lower())
#     # We use path and query to differentiate between different videos from the same channel
#     normalized_url = f"{parsed_url.netloc}{parsed_url.path}?{parsed_url.query}"
#     return hashlib.sha256(normalized_url.encode('utf-8')).hexdigest()

# def count_tokens(text: str) -> int:
#     """Count tokens using the cl100k_base tokenizer used by many embedding models."""
#     try:
#         encoding = tiktoken.get_encoding("cl100k_base")
#         return len(encoding.encode(text, disallowed_special=()))
#     except Exception:
#         return len(text.split())  # Fallback to a simple word count

# # ==============================================================================
# # 2. YOUTUBE TRANSCRIPT PROCESSING LOGIC
# # ==============================================================================

# def load_and_chunk_transcript(url: str) -> List[Document]:
#     """Load a YouTube transcript and chunk it into token-based sections."""
#     print(f"[CPU-Bound] Starting transcript processing for URL: {url}")
#     try:
#         # Using YoutubeLoader to fetch the transcript and metadata
#         loader = YoutubeLoader.from_youtube_url(url, add_video_info=True)
#         transcript_docs = loader.load()

#         if not transcript_docs:
#             print(f"Warning: No transcript found for {url}. Skipping.")
#             return []

#         # The loader returns a single Document with the full transcript.
#         full_transcript = transcript_docs[0].page_content
#         video_metadata = transcript_docs[0].metadata

#         text_splitter = RecursiveCharacterTextSplitter(
#             chunk_size=CHUNK_SIZE_TOKENS,
#             chunk_overlap=CHUNK_OVERLAP_TOKENS,
#             length_function=count_tokens,
#             is_separator_regex=False,
#         )

#         chunks = text_splitter.split_text(full_transcript)
        
#         chunked_documents = []
#         for i, chunk_text in enumerate(chunks):
#             metadata = {
#                 "source": url,
#                 "title": video_metadata.get("title", "Unknown Title"),
#                 "author": video_metadata.get("author", "Unknown Author"),
#                 "chunk_number": i + 1,
#                 "total_chunks": len(chunks),
#                 "text": chunk_text,
#                 "token_count": count_tokens(chunk_text)
#             }
#             doc = Document(page_content=chunk_text, metadata=metadata)
#             chunked_documents.append(doc)

#         print(f"[CPU-Bound] Successfully chunked transcript from {url} into {len(chunked_documents)} sections.")
#         return chunked_documents

#     except Exception as e:
#         print(f"Error processing transcript for {url}: {e}")
#         return []

# # ==============================================================================
# # 3. CORE INGESTION LOGIC
# # ==============================================================================

# async def ingest_video(pinecone_client: PineconeClient, pinecone_index_host: str,
#                        video_url: str, executor: ProcessPoolExecutor):
#     """Ingest a single YouTube video transcript into the Pinecone vector database."""
#     print("\n" + "=" * 50)
#     print(f"Processing video: {video_url}")

#     namespace = _create_namespace_from_url(video_url)

#     try:
#         pinecone_index = pinecone_client.Index(host=pinecone_index_host)
#         stats = pinecone_index.describe_index_stats()
#         if namespace in stats.namespaces and stats.namespaces[namespace].vector_count > 0:
#             print(f"Video already exists in Pinecone namespace '{namespace}'. Skipping.")
#             return
#     except Exception as e:
#         print(f"Could not connect to Pinecone index: {e}")
#         return

#     print(f"Starting new ingestion into namespace '{namespace}'...")

#     try:
#         loop = asyncio.get_running_loop()
#         # Run the CPU-bound transcript loading/chunking in a separate process
#         chunked_docs = await loop.run_in_executor(
#             executor, load_and_chunk_transcript, video_url
#         )

#         if not chunked_docs:
#             print(f"No chunks were created for {video_url}. Aborting ingestion.")
#             return

#         print(f"Total chunks to process: {len(chunked_docs)}. Processing in batches of {EMBEDDING_BATCH_SIZE}...")

#         for i in range(0, len(chunked_docs), EMBEDDING_BATCH_SIZE):
#             batch_docs = chunked_docs[i:i + EMBEDDING_BATCH_SIZE]
#             batch_num = i // EMBEDDING_BATCH_SIZE + 1

#             texts_to_embed = [doc.page_content for doc in batch_docs]
#             print(f" - Creating embeddings for batch {batch_num} ({len(texts_to_embed)} chunks)...")

#             # Embedding can be CPU-intensive, so it's also run in an executor
#             embeddings = await loop.run_in_executor(
#                 None, EMBEDDING_MODEL.embed_documents, texts_to_embed
#             )

#             ids = [f"{namespace}_chunk_{i + j}" for j in range(len(batch_docs))]
#             metadata_to_upload = [doc.metadata for doc in batch_docs]
#             vectors_to_upsert = list(zip(ids, embeddings, metadata_to_upload))

#             print(f" - Uploading {len(vectors_to_upsert)} vectors for batch {batch_num}...")
#             # The actual network I/O call is done here
#             await loop.run_in_executor(
#                 None, lambda: pinecone_index.upsert(vectors=vectors_to_upsert, namespace=namespace)
#             )

#         print(f"Successfully ingested video '{video_url}'.")

#     except Exception as e:
#         print(f"\n--- CRITICAL ERROR during ingestion for {video_url} ---")
#         import traceback
#         traceback.print_exc()
#         print("--- END ERROR ---\n")

# # ==============================================================================
# # 4. MAIN EXECUTION FUNCTIONS
# # ==============================================================================

# async def process_videos(videos_to_ingest: List[str]):
#     """Process multiple YouTube videos for ingestion concurrently."""
#     pinecone_api_key = os.getenv("PINECONE_API_KEY")

#     if not all([pinecone_api_key, PINECONE_INDEX_HOST, PINECONE_INDEX_NAME]):
#         print("Error: Ensure PINECONE_API_KEY, PINECONE_INDEX_HOST, and PINECONE_INDEX_NAME are set in your .env file.")
#         return

#     pinecone_client = PineconeClient(api_key=pinecone_api_key)

#     with ProcessPoolExecutor() as executor:
#         tasks = [
#             ingest_video(pinecone_client, PINECONE_INDEX_HOST, url, executor)
#             for url in videos_to_ingest
#         ]
#         await asyncio.gather(*tasks)

#     print("\n" + "=" * 50)
#     print("Ingestion process finished for all specified YouTube videos.")

# def run_youtube_ingestion(videos: List[str]):
#     """Main entry point for YouTube transcript ingestion."""
#     if not videos:
#         print("No YouTube video URLs provided for ingestion.")
#         return

#     print(f"Starting YouTube ingestion script for {len(videos)} videos...")
#     asyncio.run(process_videos(videos))

# without common_util file addition code



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




# yt_ingestion.py

"""
YouTube transcript ingestion system for video processing and vector storage.
This script is refactored to use a common utility module for shared logic.

It is responsible ONLY for fetching, parsing, and chunking YouTube transcripts.
"""

import os
import asyncio
from typing import List
from concurrent.futures import ProcessPoolExecutor

# Langchain imports
from langchain_community.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import YoutubeLoader

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
# Import shared logic from the common utility module
from ai.ingestion.common_utils import (
    initialize_clients,
    create_namespace_from_url,
    count_tokens,
    batch_embed_and_upsert
)

# --- YOUTUBE-SPECIFIC CONFIGURATION ---
CHUNK_SIZE_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 40

# ==============================================================================
# 1. YOUTUBE-SPECIFIC PROCESSING LOGIC
# (This section is unique to this file and remains unchanged)
# ==============================================================================

def load_and_chunk_transcript(url: str) -> List[Document]:
    """Load a YouTube transcript and chunk it into token-based sections."""
    print(f"[CPU-Bound] Starting transcript processing for URL: {url}")
    try:
        loader = YoutubeLoader.from_youtube_url(url, add_video_info=True)
        transcript_docs = loader.load()

        if not transcript_docs:
            print(f"Warning: No transcript found for {url}. Skipping.")
            return []

        full_transcript = transcript_docs[0].page_content
        video_metadata = transcript_docs[0].metadata

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE_TOKENS,
            chunk_overlap=CHUNK_OVERLAP_TOKENS,
            length_function=count_tokens,
            is_separator_regex=False,
        )

        chunks = text_splitter.split_text(full_transcript)
        
        chunked_documents = []
        for i, chunk_text in enumerate(chunks):
            metadata = {
                "source": url,
                "title": video_metadata.get("title", "Unknown Title"),
                "author": video_metadata.get("author", "Unknown Author"),
                "chunk_number": i + 1,
                "total_chunks": len(chunks),
                "text": chunk_text,
                "token_count": count_tokens(chunk_text)
            }
            doc = Document(page_content=chunk_text, metadata=metadata)
            chunked_documents.append(doc)

        print(f"[CPU-Bound] Successfully chunked transcript from {url} into {len(chunked_documents)} sections.")
        return chunked_documents

    except Exception as e:
        print(f"Error processing transcript for {url}: {e}")
        return []

# ==============================================================================
# 2. CORE INGESTION & ORCHESTRATION LOGIC
# ==============================================================================

async def ingest_video(
    pinecone_client: 'pinecone.Pinecone',
    pinecone_index_host: str,
    embedding_model: 'langchain_community.embeddings.base.Embeddings',
    video_url: str,
    executor: ProcessPoolExecutor
):
    """Orchestrates the ingestion of a single YouTube video transcript."""
    print("\n" + "=" * 50)
    print(f"Processing video: {video_url}")

    namespace = create_namespace_from_url(video_url)

    try:
        pinecone_index = pinecone_client.Index(host=pinecone_index_host)
        stats = pinecone_index.describe_index_stats()
        if namespace in stats.namespaces and stats.namespaces[namespace].vector_count > 0:
            print(f"Video already exists in Pinecone namespace '{namespace}'. Skipping.")
            return
    except Exception as e:
        print(f"Could not connect to Pinecone index: {e}")
        return

    print(f"Starting new ingestion into namespace '{namespace}'...")
    try:
        loop = asyncio.get_running_loop()
        chunked_docs = await loop.run_in_executor(
            executor, load_and_chunk_transcript, video_url
        )

        if not chunked_docs:
            print(f"No chunks were created for {video_url}. Aborting ingestion.")
            return

        # Hand off to the common utility function for embedding and upserting
        await batch_embed_and_upsert(
            pinecone_index, chunked_docs, embedding_model, namespace
        )

        print(f"Successfully ingested video '{video_url}'.")
    except Exception as e:
        print(f"\n--- CRITICAL ERROR during ingestion for {video_url} ---")
        import traceback
        traceback.print_exc()
        print("--- END ERROR ---\n")

async def process_videos(videos_to_ingest: List[str]):
    """Main async function to process multiple YouTube videos concurrently."""
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
            ingest_video(
                pinecone_client, pinecone_index_host, embedding_model,
                url, executor
            )
            for url in videos_to_ingest
        ]
        await asyncio.gather(*tasks)

    print("\n" + "=" * 50)
    print("Ingestion process finished for all specified YouTube videos.")

def run_youtube_ingestion(videos: List[str]):
    """Main entry point for YouTube transcript ingestion."""
    if not videos:
        print("No YouTube video URLs provided for ingestion.")
        return
    print(f"Starting YouTube ingestion script for {len(videos)} videos...")
    asyncio.run(process_videos(videos))
