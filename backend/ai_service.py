# backend/ai_service.py

"""
This module acts as a client to communicate with the standalone AI API.

It abstracts away the HTTP requests, making it easy for the main backend
to request AI tasks like ingestion, chat, and content generation.
"""

import os
import httpx
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv()

# Get the base URL of your AI API (the one you built with AI/main_api.py)
AI_API_BASE_URL = os.getenv("AI_API_BASE_URL", "http://localhost:8000/")

# We create a single, reusable, asynchronous HTTP client.
# This is much more efficient than creating a new client for every request.
# We set a reasonable timeout (e.g., 5 mins) for potentially long-running generation tasks.
ai_api_client = httpx.AsyncClient(base_url=AI_API_BASE_URL, timeout=300.0)

# ==============================================================================
# AI SERVICE FUNCTIONS
# ==============================================================================

async def trigger_youtube_ingestion(urls: List[str]) -> bool:
    """
    Tells the AI API to start ingesting a list of YouTube videos.
    This is a "fire-and-forget" task.
    """
    endpoint = "/ingest/youtube"
    try:
        response = await ai_api_client.post(endpoint, json={"urls": urls})
        response.raise_for_status() # Raise an exception for bad responses (4xx, 5xx)
        print(f"Successfully triggered YouTube ingestion for: {urls}")
        return True
    except httpx.HTTPStatusError as e:
        print(f"AI API returned an error for YouTube ingestion: {e}")
    except httpx.RequestError as e:
        print(f"Failed to connect to AI API for YouTube ingestion: {e}")
    return False

async def trigger_pdf_ingestion(filename: str, file_content: bytes, callback_url: str) -> bool:
    """
    Sends a PDF file to the AI API to start the ingestion process.
    This is a "fire-and-forget" task.
    """
    endpoint = "/ingest/pdf"
    
    # We must send this as 'multipart/form-data'
    files_to_upload = {'file': (filename, file_content, 'application/pdf')}
    
    data = {'callback_url': callback_url, 'source_id': filename}
    try:
        response = await ai_api_client.post(endpoint, files=files_to_upload, data=data)
        response.raise_for_status()
        print(f"Successfully triggered PDF ingestion for: {filename}")
        return True
    except httpx.HTTPStatusError as e:
        print(f"AI API returned an error for PDF ingestion: {e}")
    except httpx.RequestError as e:
        print(f"Failed to connect to AI API for PDF ingestion: {e}")
    return False

async def get_chat_response(query: str, source_id: str) -> Optional[Dict[str, Any]]:
    """
    Gets a context-aware chat response from the AI API.
    This task waits for the response.
    """
    endpoint = "/chat"
    payload = {"query": query, "source_id": source_id}
    try:
        response = await ai_api_client.post(endpoint, json=payload)
        response.raise_for_status()
        return response.json()  # Returns the dict, e.g., {"answer": "...", "sources": [...]}
    except httpx.HTTPStatusError as e:
        print(f"AI API returned an error for chat: {e}")
    except httpx.RequestError as e:
        print(f"Failed to connect to AI API for chat: {e}")
    return None

async def get_generated_notes(source_id: str) -> Optional[Dict[str, str]]:
    """
    Gets synthesized notes from the AI API.
    This task waits for the response.
    """
    endpoint = "/generate/notes"
    payload = {"source_id": source_id}
    try:
        response = await ai_api_client.post(endpoint, json=payload)
        response.raise_for_status()
        return response.json() # Returns the dict, e.g., {"notes": "..."}
    except httpx.HTTPStatusError as e:
        print(f"AI API returned an error for notes generation: {e}")
    except httpx.RequestError as e:
        print(f"Failed to connect to AI API for notes generation: {e}")
    return None

async def get_generated_study_plan(source_id: str, knowledge_level: str, learning_style: str) -> Optional[Dict[str, str]]:
    """
    Gets a personalized study plan from the AI API.
    This task waits for the response.
    """
    endpoint = "/generate/study_plan"
    payload = {
        "source_id": source_id,
        "knowledge_level": knowledge_level,
        "learning_style": learning_style
    }
    try:
        response = await ai_api_client.post(endpoint, json=payload)
        response.raise_for_status()
        return response.json() # Returns the dict, e.g., {"study_plan": "..."}
    except httpx.HTTPStatusError as e:
        print(f"AI API returned an error for study plan generation: {e}")
    except httpx.RequestError as e:
        print(f"Failed to connect to AI API for study plan generation: {e}")
    return None

async def close_ai_client():
    """A helper function to close the client on app shutdown."""
    await ai_api_client.aclose()