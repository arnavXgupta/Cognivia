# # yt_ingestion.py

# """
# YouTube transcript ingestion system for video processing and vector storage.
# This script is refactored to use a common utility module for shared logic.

# It is responsible ONLY for fetching, parsing, and chunking YouTube transcripts.
# """
# import os
# import asyncio
# from typing import List, Optional
# from youtube_transcript_api import YouTubeTranscriptApi
# import re

# # Langchain imports
# from langchain_community.docstore.document import Document
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_community.document_loaders import YoutubeLoader

# import sys
# sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
# # Import shared logic from the common utility module
# from ai.ingestion.common_utils import (
#     initialize_clients,
#     create_namespace_from_url,
#     count_tokens,
#     batch_embed_and_upsert
# )

# # --- YOUTUBE-SPECIFIC CONFIGURATION ---
# CHUNK_SIZE_TOKENS = 400
# CHUNK_OVERLAP_TOKENS = 40

# # ==============================================================================
# # 1. YOUTUBE-SPECIFIC PROCESSING LOGIC WITH ENHANCED ERROR HANDLING
# # ==============================================================================

# def load_and_chunk_transcript(url: str, use_proxy: bool = False, proxies: Optional[dict] = None) -> List[Document]:
#     """
#     Load a YouTube transcript and chunk it into token-based sections.
#     Includes robust fallback mechanism for HTTP 400 errors.
    
#     Args:
#         url: YouTube video URL
#         use_proxy: Whether to use proxy for transcript fetching
#         proxies: Dictionary of proxy settings (e.g., {'http': 'socks5://...', 'https': 'socks5://...'})
    
#     Returns:
#         List of Document objects with chunked transcript
#     """
#     print(f"[Processing] Starting transcript extraction for: {url}")
    
#     # Extract video ID from URL
#     video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
#     if not video_id_match:
#         print(f"[Error] Invalid YouTube URL format: {url}")
#         return []
    
#     video_id = video_id_match.group(1)
#     full_transcript = None
#     video_metadata = {}
    
#     # METHOD 1: Try youtube_transcript_api FIRST (more reliable for cloud/server environments)
#     try:
#         print(f"[Attempting] Method 1: Direct youtube_transcript_api")
        
#         if use_proxy and proxies:
#             print(f"[Info] Using proxy configuration")
#             transcript_list = YouTubeTranscriptApi.get_transcript(video_id, proxies=proxies)
#         else:
#             transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        
#         full_transcript = " ".join([entry["text"] for entry in transcript_list])
        
#         # Basic metadata (you can enhance this with additional API calls if needed)
#         video_metadata = {
#             "title": f"Video {video_id}",
#             "author": "Unknown Author",
#             "source": url,
#             "video_id": video_id
#         }
#         print(f"[Success] ✓ Transcript loaded via youtube_transcript_api")
        
#     except Exception as e:
#         print(f"[Warning] youtube_transcript_api failed: {type(e).__name__}: {e}")
#         print(f"[Attempting] Method 2: Fallback to LangChain's YoutubeLoader")
        
#         # METHOD 2: Try LangChain's YoutubeLoader as fallback
#         try:
#             loader = YoutubeLoader.from_youtube_url(url, add_video_info=True)
#             transcript_docs = loader.load()
            
#             if transcript_docs and len(transcript_docs) > 0:
#                 full_transcript = transcript_docs[0].page_content
#                 video_metadata = transcript_docs[0].metadata
#                 print(f"[Success] ✓ Transcript loaded via YoutubeLoader fallback")
#             else:
#                 raise ValueError("No transcript returned from YoutubeLoader")
                
#         except Exception as fallback_error:
#             print(f"[Error] ✗ Both transcript extraction methods failed")
#             print(f"[Error] Method 1 (youtube_transcript_api): {type(e).__name__}")
#             print(f"[Error] Method 2 (YoutubeLoader): {type(fallback_error).__name__}: {fallback_error}")
#             print(f"[Suggestion] If running on cloud/server:")
#             print(f"  1. Check if YouTube is blocking your server IP")
#             print(f"  2. Consider using proxies (see documentation)")
#             print(f"  3. Try running locally first to verify video has transcripts")
#             return []
    
#     # Validate transcript content
#     if not full_transcript or len(full_transcript.strip()) == 0:
#         print(f"[Error] Empty transcript retrieved for {url}")
#         return []
    
#     print(f"[Info] Transcript length: {len(full_transcript)} characters")
    
#     # Chunk the transcript
#     try:
#         text_splitter = RecursiveCharacterTextSplitter(
#             chunk_size=CHUNK_SIZE_TOKENS,
#             chunk_overlap=CHUNK_OVERLAP_TOKENS,
#             length_function=count_tokens,
#             is_separator_regex=False,
#         )
        
#         chunks = text_splitter.split_text(full_transcript)
        
#         if not chunks:
#             print(f"[Error] Text splitter produced no chunks for {url}")
#             return []
        
#         # Create Document objects with metadata
#         chunked_documents = []
#         for i, chunk_text in enumerate(chunks):
#             metadata = {
#                 "source": url,
#                 "title": video_metadata.get("title", "Unknown Title"),
#                 "author": video_metadata.get("author", "Unknown Author"),
#                 "video_id": video_id,
#                 "chunk_number": i + 1,
#                 "total_chunks": len(chunks),
#                 "text": chunk_text,
#                 "token_count": count_tokens(chunk_text)
#             }
#             doc = Document(page_content=chunk_text, metadata=metadata)
#             chunked_documents.append(doc)
        
#         total_tokens = sum(count_tokens(c) for c in chunks)
#         print(f"[Success] ✓ Chunked transcript into {len(chunked_documents)} sections")
#         print(f"[Info] Total tokens: {total_tokens}")
#         return chunked_documents
        
#     except Exception as e:
#         print(f"[Error] Failed to chunk transcript for {url}: {e}")
#         import traceback
#         traceback.print_exc()
#         return []

# # ==============================================================================
# # 2. CORE INGESTION & ORCHESTRATION LOGIC
# # ==============================================================================

# async def ingest_video(
#     pinecone_index: 'pinecone.Index',
#     embedding_model: 'langchain_community.embeddings.base.Embeddings',
#     video_url: str,
#     use_proxy: bool = False,
#     proxies: Optional[dict] = None
# ):
#     """
#     Orchestrates the ingestion of a single YouTube video transcript.
    
#     Args:
#         pinecone_index: Pinecone index instance
#         embedding_model: Embedding model instance
#         video_url: YouTube video URL
#         use_proxy: Whether to use proxy
#         proxies: Proxy configuration dictionary
#     """
#     print("\n" + "=" * 70)
#     print(f"Processing video: {video_url}")
#     print("=" * 70)
    
#     namespace = create_namespace_from_url(video_url)
    
#     # Check if video already exists in Pinecone
#     try:
#         stats = pinecone_index.describe_index_stats()
#         if namespace in stats.get('namespaces', {}) and stats['namespaces'][namespace].get('vector_count', 0) > 0:
#             print(f"[Skip] Video already exists in namespace '{namespace}'")
#             print(f"[Info] Current vector count: {stats['namespaces'][namespace]['vector_count']}")
#             return
#     except Exception as e:
#         print(f"[Error] Could not check Pinecone index stats: {e}")
#         print(f"[Continuing] Proceeding with ingestion anyway...")
    
#     print(f"[Starting] New ingestion into namespace '{namespace}'...")
    
#     # Load and chunk transcript
#     try:
#         chunked_docs = load_and_chunk_transcript(video_url, use_proxy=use_proxy, proxies=proxies)
        
#         if not chunked_docs:
#             print(f"[Error] No chunks were created for {video_url}")
#             print(f"[Aborted] Skipping ingestion for this video")
#             return
        
#         print(f"[Info] Ready to embed and upsert {len(chunked_docs)} chunks")
        
#     except Exception as e:
#         print(f"[Error] Transcript loading failed for {video_url}")
#         print(f"[Error Details] {type(e).__name__}: {e}")
#         import traceback
#         traceback.print_exc()
#         return
    
#     # Embed and upsert to Pinecone (async I/O-bound work)
#     try:
#         await batch_embed_and_upsert(
#             pinecone_index, 
#             chunked_docs, 
#             embedding_model, 
#             namespace
#         )
        
#         print(f"[Success] ✓ Successfully ingested video: {video_url}")
#         print(f"[Success] ✓ Namespace: {namespace}")
#         print(f"[Success] ✓ Total chunks: {len(chunked_docs)}")
        
#     except Exception as e:
#         print(f"[Error] Failed to embed/upsert for {video_url}")
#         print(f"[Error Details] {type(e).__name__}: {e}")
#         import traceback
#         traceback.print_exc()

# async def process_videos(videos_to_ingest: List[str], use_proxy: bool = False, proxies: Optional[dict] = None):
#     """
#     Main async function to process multiple YouTube videos concurrently.
    
#     Args:
#         videos_to_ingest: List of YouTube video URLs
#         use_proxy: Whether to use proxy for transcript fetching
#         proxies: Proxy configuration (e.g., {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'})
#     """
#     print("\n" + "=" * 70)
#     print(f"YOUTUBE INGESTION STARTED")
#     print(f"Total videos to process: {len(videos_to_ingest)}")
#     if use_proxy:
#         print(f"[Info] Proxy mode: ENABLED")
#     print("=" * 70)
    
#     # Initialize clients once
#     try:
#         pinecone_client, embedding_model = initialize_clients()
#         pinecone_index_host = os.getenv("PINECONE_INDEX_HOST")
        
#         if not pinecone_index_host:
#             raise ValueError("PINECONE_INDEX_HOST environment variable is not set")
        
#         pinecone_index = pinecone_client.Index(host=pinecone_index_host)
#         print(f"[Success] ✓ Initialized Pinecone and embedding model")
        
#     except Exception as e:
#         print(f"[Error] Initialization failed: {e}")
#         import traceback
#         traceback.print_exc()
#         return
    
#     # Process all videos concurrently
#     tasks = [
#         ingest_video(pinecone_index, embedding_model, url, use_proxy=use_proxy, proxies=proxies)
#         for url in videos_to_ingest
#     ]
    
#     # Gather results and capture exceptions
#     results = await asyncio.gather(*tasks, return_exceptions=True)
    
#     # Summary report
#     print("\n" + "=" * 70)
#     print("INGESTION SUMMARY")
#     print("=" * 70)
    
#     success_count = 0
#     failed_count = 0
    
#     for url, result in zip(videos_to_ingest, results):
#         if isinstance(result, Exception):
#             print(f"[Failed] ✗ {url}")
#             print(f"  Error: {type(result).__name__}: {result}")
#             failed_count += 1
#         else:
#             success_count += 1
    
#     print(f"\n[Summary] Successfully processed: {success_count}/{len(videos_to_ingest)}")
#     print(f"[Summary] Failed: {failed_count}/{len(videos_to_ingest)}")
#     print("=" * 70)
#     print("INGESTION PROCESS COMPLETED")
#     print("=" * 70 + "\n")

# def run_youtube_ingestion(videos: List[str], use_proxy: bool = False, proxies: Optional[dict] = None):
#     """
#     Main entry point for YouTube transcript ingestion.
    
#     Args:
#         videos: List of YouTube video URLs to process
#         use_proxy: Set to True if running on cloud/server and experiencing HTTP 400 errors
#         proxies: Proxy configuration dict. Example:
#                  {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'}
#                  See documentation for proxy setup: https://github.com/jdepoix/youtube-transcript-api
    
#     Examples:
#         # Basic usage (local environment)
#         run_youtube_ingestion(['https://www.youtube.com/watch?v=...'])
        
#         # With Tor proxy (for cloud/server environments)
#         proxies = {
#             'http': 'socks5://127.0.0.1:9050',
#             'https': 'socks5://127.0.0.1:9050'
#         }
#         run_youtube_ingestion(['https://www.youtube.com/watch?v=...'], use_proxy=True, proxies=proxies)
#     """
#     if not videos:
#         print("[Error] No YouTube video URLs provided for ingestion")
#         return
    
#     print(f"\n[Starting] YouTube ingestion script")
#     print(f"[Info] Videos to process: {len(videos)}")
    
#     try:
#         asyncio.run(process_videos(videos, use_proxy=use_proxy, proxies=proxies))
#     except KeyboardInterrupt:
#         print("\n[Interrupted] Ingestion cancelled by user")
#     except Exception as e:
#         print(f"\n[Error] Unexpected error in main execution: {e}")
#         import traceback
#         traceback.print_exc()




# yt_ingestion.py

"""
YouTube transcript ingestion system for video processing and vector storage.
This script is refactored to use a common utility module for shared logic.

It is responsible ONLY for fetching, parsing, and chunking YouTube transcripts.
"""
import os
import asyncio
from typing import List, Optional
from youtube_transcript_api import YouTubeTranscriptApi
import re

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
# 1. YOUTUBE-SPECIFIC PROCESSING LOGIC WITH ENHANCED ERROR HANDLING
# ==============================================================================

def load_and_chunk_transcript(url: str, use_proxy: bool = False, proxies: Optional[dict] = None) -> List[Document]:
    """
    Load a YouTube transcript and chunk it into token-based sections.
    Includes robust fallback mechanism for HTTP 400 errors.

    Args:
        url: YouTube video URL
        use_proxy: Whether to use proxy for transcript fetching
        proxies: Dictionary of proxy settings (e.g., {'http': 'socks5://...', 'https': 'socks5://...'})

    Returns:
        List of Document objects with chunked transcript
    """
    print(f"[Processing] Starting transcript extraction for: {url}")

    # Extract video ID from URL
    video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
    if not video_id_match:
        print(f"[Error] Invalid YouTube URL format: {url}")
        return []

    video_id = video_id_match.group(1)
    transcript_text = ""
    video_metadata = {}

    # ==========================================
    # METHOD 1: Direct youtube_transcript_api (FIXED)
    # ==========================================
    try:
        print("[Attempting] Method 1: Direct youtube_transcript_api")

        # FIXED: Use list_transcripts() instead of get_transcript()
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Try to find English transcript first
        try:
            transcript = transcript_list.find_transcript(['en'])
        except:
            # If no English, get the first available transcript
            transcript = transcript_list.find_generated_transcript(['en'])

        # Fetch the actual transcript data
        transcript_data = transcript.fetch()

        # Combine all transcript segments
        transcript_text = " ".join([entry['text'] for entry in transcript_data])

        # Get video metadata using YoutubeLoader (just for metadata)
        try:
            loader = YoutubeLoader.from_youtube_url(url, add_video_info=True)
            docs = loader.load()
            if docs:
                video_metadata = docs[0].metadata
        except Exception as e:
            print(f"[Warning] Could not fetch metadata: {e}")
            video_metadata = {"title": "Unknown Title", "author": "Unknown Author"}

        print("[Success] ✓ Transcript extracted using youtube_transcript_api")

    except AttributeError as e:
        print(f"[Warning] youtube_transcript_api failed: AttributeError: {e}")
        transcript_text = ""
    except Exception as e:
        print(f"[Warning] youtube_transcript_api failed: {type(e).__name__}: {e}")
        transcript_text = ""

    # ==========================================
    # METHOD 2: Fallback to LangChain's YoutubeLoader
    # ==========================================
    if not transcript_text:
        try:
            print("[Attempting] Method 2: Fallback to LangChain's YoutubeLoader")
            loader = YoutubeLoader.from_youtube_url(url, add_video_info=True)
            docs = loader.load()

            if docs:
                transcript_text = docs[0].page_content
                video_metadata = docs[0].metadata
                print("[Success] ✓ Transcript extracted using YoutubeLoader")
            else:
                print("[Warning] YoutubeLoader returned no documents")

        except Exception as e:
            print(f"[Warning] YoutubeLoader failed: {type(e).__name__}: {e}")

    # ==========================================
    # ERROR HANDLING: Both methods failed
    # ==========================================
    if not transcript_text:
        print("[Error] ✗ Both transcript extraction methods failed")
        print("[Error] Method 1 (youtube_transcript_api): AttributeError")
        print("[Error] Method 2 (YoutubeLoader): HTTPError: HTTP Error 400: Bad Request")
        print("[Suggestion] If running on cloud/server:")
        print("  1. Check if YouTube is blocking your server IP")
        print("  2. Consider using proxies (see documentation)")
        print("  3. Try running locally first to verify video has transcripts")
        return []

    # ==========================================
    # CHUNKING: Split transcript into token-based chunks
    # ==========================================
    print(f"[Chunking] Splitting transcript (length: {len(transcript_text)} chars)")

    # FIXED: Removed trailing comma from is_separator_regex parameter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE_TOKENS,
        chunk_overlap=CHUNK_OVERLAP_TOKENS,
        length_function=count_tokens,
        is_separator_regex=False
    )

    chunks = text_splitter.split_text(transcript_text)
    print(f"[Chunking] Created {len(chunks)} chunks")

    # ==========================================
    # CREATE DOCUMENT OBJECTS: Format chunks with metadata
    # ==========================================
    documents = []
    for i, chunk_text in enumerate(chunks):
        # FIXED: Removed 'text' field from metadata to avoid conflicts
        metadata = {
            "source": url,
            "title": video_metadata.get("title", "Unknown Title"),
            "author": video_metadata.get("author", "Unknown Author"),
            "video_id": video_id,
            "chunk_number": i + 1,
            "total_chunks": len(chunks),
            "token_count": count_tokens(chunk_text)
        }

        doc = Document(
            page_content=chunk_text,
            metadata=metadata
        )
        documents.append(doc)

    print(f"[Success] ✓ Created {len(documents)} document chunks")
    return documents


# ==============================================================================
# 2. MAIN YOUTUBE INGESTION ORCHESTRATION
# ==============================================================================

async def ingest_video(url: str, use_proxy: bool = False, proxies: Optional[dict] = None):
    """
    Ingest a single YouTube video into the vector store.

    Args:
        url: YouTube video URL
        use_proxy: Whether to use proxy for requests
        proxies: Proxy configuration dictionary
    """
    print(f"Processing video: {url}")
    print("=" * 70)

    # Create namespace from URL
    namespace = create_namespace_from_url(url)
    print(f"[Starting] New ingestion into namespace '{namespace}'...")

    # Initialize clients (Pinecone & FastEmbed)
    pinecone_index, embedding_model = initialize_clients()

    # Load and chunk the transcript
    chunks = load_and_chunk_transcript(url, use_proxy=use_proxy, proxies=proxies)

    if not chunks:
        print(f"[Error] No chunks were created for {url}")
        print(f"[Aborted] Skipping ingestion for this video")
        return

    # Batch embed and upsert to Pinecone
    await batch_embed_and_upsert(
        chunks=chunks,
        embedding_model=embedding_model,
        pinecone_index=pinecone_index,
        namespace=namespace
    )

    print(f"[Complete] ✓ Successfully ingested: {url}")


def run_youtube_ingestion(video_urls: List[str], use_proxy: bool = False, proxies: Optional[dict] = None):
    """
    Main entry point for YouTube transcript ingestion.

    Args:
        video_urls: List of YouTube video URLs to process
        use_proxy: Whether to use proxy for requests
        proxies: Proxy configuration (e.g., {'http': 'socks5://127.0.0.1:9050', 'https': 'socks5://127.0.0.1:9050'})
    """
    print("\n" + "=" * 70)
    print("STARTING YOUTUBE TRANSCRIPT INGESTION")
    print("=" * 70)
    print(f"[Config] Total videos to process: {len(video_urls)}")
    print(f"[Config] Proxy enabled: {use_proxy}")
    print("=" * 70 + "\n")

    successful = 0
    failed = 0

    for url in video_urls:
        try:
            asyncio.run(ingest_video(url, use_proxy=use_proxy, proxies=proxies))
            successful += 1
        except Exception as e:
            print(f"[Error] Failed to process {url}: {e}")
            failed += 1

        print()  # Blank line between videos

    # Print summary
    print("=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    print(f"[Summary] Successfully processed: {successful}/{len(video_urls)}")
    print(f"[Summary] Failed: {failed}/{len(video_urls)}")
    print("=" * 70)
    print("INGESTION PROCESS COMPLETED")

