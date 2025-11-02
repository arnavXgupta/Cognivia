# AI/main_api.py

"""
FastAPI application to serve the AI co-pilot's core functionalities.

This API provides endpoints for:
1. Ingesting YouTube videos.
2. Ingesting PDF documents.
3. Chatting with an ingested source (RAG).
4. Generating synthesized notes from a source.
5. Generating a personalized study plan from a source.
"""

import os
import asyncio
from contextlib import asynccontextmanager
from typing import List, Dict, Any

# FastAPI and Pydantic
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".", ".."))

# Import your core AI logic
from ai.core.chatbot import ContextualChatbot
from ai.core.generation_task import ContentGenerator
from ai.core.llm_connector import get_llm
from ai.ingestion.common_utils import initialize_clients, get_embedding_model

# Import your ingestion runners
from ai.ingestion.yt_ingestion import run_youtube_ingestion
from ai.ingestion.pdf_ingestion import run_ingestion_from_uploads

# ==============================================================================
# 1. LIFESPAN MANAGEMENT (FOR MODEL LOADING)
# ==============================================================================

# This dictionary will hold our AI models, loaded on startup.
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     print("AI API Startup: Loading core AI modules...")
#     try:
#         app.state.chatbot = ContextualChatbot()
#         app.state.generator = ContentGenerator()
#         print("AI core modules loaded successfully.")
#     except Exception as e:
#         print(f"FATAL: AI core modules failed to load: {e}")
#         raise RuntimeError(f"Failed to initialize AI models: {e}")
    
#     yield
#     print("AI API Shutdown.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("AI API Startup: Loading core AI modules...")
    try:
        # 1. Load models ONCE
        llm_instance = get_llm()
        if not llm_instance:
            raise RuntimeError("Failed to get LLM instance. Is Ollama running?")

        embedding_model_instance = get_embedding_model()
        pinecone_client_instance = initialize_clients()

        # 2. Pass them into the classes
        app.state.chatbot = ContextualChatbot(
            llm=llm_instance,
            embedding_model=embedding_model_instance,
            pinecone_client=pinecone_client_instance
        )
        app.state.generator = ContentGenerator(
            llm=llm_instance,
            embedding_model=embedding_model_instance,
            pinecone_client=pinecone_client_instance
        )
        print("AI core modules loaded successfully (single instances).")

    except Exception as e:
        print(f"FATAL: AI core modules failed to load: {e}")
        raise RuntimeError(f"Failed to initialize AI models: {e}")

    yield

    print("AI API Shutdown.")

# Initialize the FastAPI app with the lifespan manager
app = FastAPI(
    title="AI Learning Co-Pilot API",
    description="API for managing data ingestion and AI-powered learning tasks.",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://localhost:8008"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 2. PYDANTIC MODELS (DATA CONTRACTS)
# ==============================================================================

# These models validate the incoming request data.
class YouTubeIngestRequest(BaseModel):
    urls: List[HttpUrl] # Pydantic validates that these are proper URLs

class ChatRequest(BaseModel):
    query: str
    source_id: str # The unique ID for the learning folder (filename or URL)

class StudyPlanRequest(BaseModel):
    source_id: str
    knowledge_level: str
    learning_style: str

class SourceRequest(BaseModel):
    source_id: str

# ==============================================================================
# 3. API ENDPOINTS
# ==============================================================================

# --- INGESTION ENDPOINTS (ASYNCHRONOUS) ---

@app.post("/ingest/youtube")
async def ingest_youtube(request: YouTubeIngestRequest, background_tasks: BackgroundTasks):
    """
    Starts the ingestion process for a list of YouTube videos in the background.
    Responds immediately.
    """
    print(f"Received ingestion request for {len(request.urls)} YouTube videos.")
    # Convert Pydantic HttpUrl objects back to simple strings for the script
    urls_list = [str(url) for url in request.urls]
    
    # Run the ingestion in the background so the API can respond immediately
    background_tasks.add_task(run_youtube_ingestion, urls_list)
    
    return {"message": f"Started ingestion for {len(urls_list)} YouTube videos."}

@app.post("/ingest/pdf")
async def ingest_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Starts the ingestion process for a single uploaded PDF file in the background.
    Responds immediately with the source_id (filename).
    """
    print(f"Received ingestion request for PDF: {file.filename}")
    
    try:
        # Read the file content as bytes
        file_content = await file.read()
        
        # Prepare the file tuple that our script expects
        file_tuple = (file.filename, file_content)
        
        # Run the ingestion in the background
        background_tasks.add_task(run_ingestion_from_uploads, [file_tuple])
        
        return {
            "message": "Started ingestion for PDF.",
            "source_id": file.filename # Return the filename as the ID
        }
    except Exception as e:
        print(f"Error reading or processing PDF file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {e}")

# --- AI CORE ENDPOINTS (SYNCHRONOUS RESPONSE) ---

@app.post("/chat")
async def chat(request: ChatRequest, fast_api_request: Request) -> Dict[str, Any]:
    """
    Handles a user's chat query using the RAG pipeline.
    Responds with the AI's answer and the sources used.
    """
    print(f"Received chat query for source: {request.source_id}")
    try:
        # Get the pre-loaded chatbot instance from the app's state
        chatbot = fast_api_request.app.state.chatbot
        
        # Call the chatbot's 'ask' method
        response = chatbot.ask(request.query, request.source_id)
        
        return response
    except Exception as e:
        print(f"Error during chat query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing chat: {e}")

@app.post("/generate/notes")
async def generate_notes(request: SourceRequest, fast_api_request: Request) -> Dict[str, str]:
    """
    Generates synthesized notes from the entire context of a source.
    """
    print(f"Received notes generation request for source: {request.source_id}")
    try:
        # Get the pre-loaded generator instance
        generator = fast_api_request.app.state.generator
        
        notes = generator.generate_notes(request.source_id)
        
        return {"notes": notes}
    except Exception as e:
        print(f"Error during notes generation: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating notes: {e}")

@app.post("/generate/study_plan")
async def generate_study_plan(request: StudyPlanRequest, fast_api_request: Request) -> Dict[str, str]:
    """
    Generates a personalized study plan from the entire context of a source.
    """
    print(f"Received study plan request for source: {request.source_id}")
    try:
        # Get the pre-loaded generator instance
        generator = fast_api_request.app.state.generator
        
        plan = generator.generate_study_plan(
            source_url_or_filename=request.source_id,
            knowledge_level=request.knowledge_level,
            learning_style=request.learning_style
        )
        
        return {"study_plan": plan}
    except Exception as e:
        print(f"Error during study plan generation: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating study plan: {e}")
    
@app.get("/")
def read_root():
    return {"message": "Welcome to the Cognivia AI Learning Co-Pilot API!"}

@app.get("/health")
def read_health():
    return {"message": "Server is Healthy babes"}

# ==============================================================================
# 4. RUN THE SERVER
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    import multiprocessing
    
    # Ensure multiprocessing works correctly when run as a script
    multiprocessing.freeze_support() 
    
    print("Starting AI API server...")
    # Run the server with auto-reload for development
    uvicorn.run("main_api:app", host="0.0.0.0", port=8000, reload=False)
