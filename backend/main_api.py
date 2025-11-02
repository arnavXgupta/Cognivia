# backend/main_api.py

"""
Main FastAPI application for the Learning Co-Pilot Backend.

This API serves as the central point of contact for the frontend.
It handles:
- Managing users (stubbed for now).
- Managing Learning Folders and Resources (database operations).
- Delegating AI tasks (chat, ingestion, generation) to the AI microservice.
"""

import os
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

# FastAPI and Pydantic
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".", ".."))

# Import from our backend modules
from backend.database import (
    create_db_and_tables, 
    get_session, 
    LearningFolder, 
    Resource
)
from backend import ai_service # Import the module itself to call its functions

# ==============================================================================
# 1. API LIFESPAN MANAGEMENT
# ==============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application's lifespan.
    - On startup: Creates the database and tables.
    - On shutdown: Gracefully closes the AI service's HTTP client.
    """
    print("Backend API Startup: Creating database tables...")
    create_db_and_tables()
    print("Database tables created.")
    
    yield
    
    print("Backend API Shutdown: Closing AI service client...")
    await ai_service.close_ai_client()
    print("AI service client closed.")

# Initialize the FastAPI app
app = FastAPI(
    title="Learning Co-Pilot Backend API",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 2. PYDANTIC MODELS (Request/Response Shapes)
# ==============================================================================

# These models define the shape of data for API requests and responses.

class FolderCreateRequest(BaseModel):
    name: str

class FolderResponse(BaseModel):
    id: int
    name: str

class ResourceResponse(BaseModel):
    id: int
    resource_type: str
    source_id: str
    folder_id: int

class FolderDetailResponse(FolderResponse):
    resources: List[ResourceResponse] = []

class YouTubeAddRequest(BaseModel):
    urls: List[str]

class ChatRequest(BaseModel):
    query: str

class StudyPlanRequest(BaseModel):
    knowledge_level: str = "beginner"
    learning_style: str = "active"

# ==============================================================================
# 3. API ENDPOINTS - LEARNING FOLDERS
# ==============================================================================

@app.post("/folders", response_model=FolderResponse)
async def create_learning_folder(
    request: FolderCreateRequest, 
    session: Session = Depends(get_session)
):
    """
    Creates a new, empty learning folder.
    """
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Folder name cannot be empty")
    
    try:
        new_folder = LearningFolder(name=request.name.strip())
        session.add(new_folder)
        session.commit()
        session.refresh(new_folder)
        return new_folder
    except Exception as e:
        session.rollback()
        print(f"Error creating folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create folder: {str(e)}")

@app.get("/folders", response_model=List[FolderResponse])
async def get_all_folders(session: Session = Depends(get_session)):
    """
    Retrieves all learning folders.
    """
    folders = session.exec(select(LearningFolder)).all()
    return folders

@app.get("/folders/{folder_id}", response_model=FolderDetailResponse)
async def get_folder_details(folder_id: int, session: Session = Depends(get_session)):
    """
    Retrieves details for a single folder, including its list of resources.
    """
    folder = session.get(LearningFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    # Manually construct the response to include resources
    return FolderDetailResponse(
        id=folder.id,
        name=folder.name,
        resources=[ResourceResponse(
            id=r.id, 
            resource_type=r.resource_type, 
            source_id=r.source_id,
            folder_id=r.folder_id
        ) for r in folder.resources]
    )

@app.delete("/folders/{folder_id}")
async def delete_folder(folder_id: int, session: Session = Depends(get_session)):
    """
    Deletes a folder and all its resources.
    """
    folder = session.get(LearningFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    session.delete(folder)
    session.commit()
    return {"message": "Folder deleted successfully"}

@app.delete("/resources/{resource_id}")
async def delete_resource(resource_id: int, session: Session = Depends(get_session)):
    """
    Deletes a resource from a folder.
    """
    resource = session.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    session.delete(resource)
    session.commit()
    return {"message": "Resource deleted successfully"}

# ==============================================================================
# 4. API ENDPOINTS - RESOURCE MANAGEMENT & INGESTION
# ==============================================================================

@app.post("/folders/{folder_id}/add-youtube", response_model=ResourceResponse)
async def add_youtube_resource(
    folder_id: int, 
    request: YouTubeAddRequest, 
    session: Session = Depends(get_session)
):
    """
    Adds a YouTube video resource to a folder and triggers AI ingestion.
    (Note: This example adds the first URL. A real app might add all.)
    """
    folder = session.get(LearningFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    if not request.urls or len(request.urls) == 0:
        raise HTTPException(status_code=400, detail="At least one URL is required")

    try:
        # 1. Call the AI service to *start* the ingestion
        success = await ai_service.trigger_youtube_ingestion(request.urls)
        if not success:
            raise HTTPException(status_code=500, detail="AI service failed to start ingestion.")

        # 2. If ingestion is triggered, add the resource(s) to our database
        # For this example, we'll just add the first URL
        url = request.urls[0]
        
        # Check if this resource already exists in this folder
        existing = session.exec(
            select(Resource).where(
                Resource.folder_id == folder.id,
                Resource.source_id == url,
                Resource.resource_type == "youtube"
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400, 
                detail=f"This YouTube URL already exists in this folder"
            )
        
        # Use original URL as source_id so AI service can find it
        new_resource = Resource(
            resource_type="youtube",
            source_id=url,  # Use original URL for AI compatibility
            folder_id=folder.id
        )
        session.add(new_resource)
        session.commit()
        session.refresh(new_resource)
        
        return new_resource
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        print(f"Error adding YouTube resource: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add resource: {str(e)}")

@app.post("/folders/{folder_id}/upload-pdf", response_model=ResourceResponse)
async def upload_pdf_resource(
    folder_id: int, 
    file: UploadFile = File(...), 
    session: Session = Depends(get_session)
):
    """
    Adds a PDF resource to a folder and triggers AI ingestion.
    """
    folder = session.get(LearningFolder, folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    try:
        file_content = await file.read()
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")

        # Check if this resource already exists in this folder
        existing = session.exec(
            select(Resource).where(
                Resource.folder_id == folder.id,
                Resource.source_id == file.filename,
                Resource.resource_type == "pdf"
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400, 
                detail=f"Resource '{file.filename}' already exists in this folder"
            )

        # 1. Call the AI service to *start* the ingestion (use original filename for AI)
        # The AI service uses the filename to create a namespace in Pinecone
        success = await ai_service.trigger_pdf_ingestion(file.filename, file_content)
        if not success:
            raise HTTPException(status_code=500, detail="AI service failed to start ingestion.")

        # 2. If ingestion is triggered, add the resource to our database
        # Use original filename as source_id so AI service can find it
        new_resource = Resource(
            resource_type="pdf",
            source_id=file.filename,  # Use original filename for AI compatibility
            folder_id=folder.id
        )
        session.add(new_resource)
        session.commit()
        session.refresh(new_resource)

        return new_resource
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        print(f"Error uploading PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload resource: {str(e)}")

# ==============================================================================
# 5. API ENDPOINTS - AI TASK PROXY
# ==============================================================================

@app.post("/resources/{resource_id}/chat")
async def chat_with_resource(
    resource_id: int, 
    request: ChatRequest, 
    session: Session = Depends(get_session)
):
    """
    Proxies a chat request to the AI API for a specific resource.
    """
    resource = session.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    response = await ai_service.get_chat_response(request.query, resource.source_id)
    if not response:
        raise HTTPException(status_code=500, detail="AI service failed to respond.")
    
    return response

@app.post("/resources/{resource_id}/generate-notes")
async def get_notes_for_resource(
    resource_id: int, 
    session: Session = Depends(get_session)
):
    """
    Proxies a notes generation request to the AI API.
    """
    resource = session.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    response = await ai_service.get_generated_notes(resource.source_id)
    if not response:
        raise HTTPException(status_code=500, detail="AI service failed to generate notes.")
    
    return response

@app.post("/resources/{resource_id}/generate-study-plan")
async def get_plan_for_resource(
    resource_id: int, 
    request: StudyPlanRequest, 
    session: Session = Depends(get_session)
):
    """
    Proxies a study plan generation request to the AI API.
    """
    resource = session.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    
    response = await ai_service.get_generated_study_plan(
        resource.source_id, 
        request.knowledge_level, 
        request.learning_style
    )
    if not response:
        raise HTTPException(status_code=500, detail="AI service failed to generate study plan.")
    
    return response

@app.get("/")
def read_root():
    return {"message": "Welcome to the Cognivia AI Backend"}

# ==============================================================================
# 6. RUN THE SERVER
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    # This server should run on a different port than the AI API
    # e.g., AI on 8000, Backend on 8008
    PORT = int(os.getenv("BACKEND_PORT", 8008))
    print(f"Starting Backend API server on http://localhost:{PORT}")
    uvicorn.run("main_api:app", host="0.0.0.0", port=PORT, reload=True)