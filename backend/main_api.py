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
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from bson.errors import InvalidId

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".", ".."))

# Import from our backend modules
from backend.database import (
    init_db,
    close_db,
    get_database,
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
    - On startup: Initializes MongoDB connection.
    - On shutdown: Closes MongoDB and AI service client.
    """
    print("Backend API Startup: Connecting to MongoDB...")
    await init_db()
    print("MongoDB connected.")
    
    yield
    
    print("Backend API Shutdown: Closing connections...")
    await close_db()
    await ai_service.close_ai_client()
    print("Shutdown complete.")

# Initialize the FastAPI app
app = FastAPI(
    title="Learning Co-Pilot Backend API",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],  
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
    id: str  # Changed from int to str for ObjectId
    name: str

class ResourceResponse(BaseModel):
    id: str  # Changed from int to str for ObjectId
    resource_type: str
    source_id: str
    folder_id: Optional[str] = None

class FolderDetailResponse(FolderResponse):
    resources: List[ResourceResponse] = []

class YouTubeAddRequest(BaseModel):
    urls: List[str]

class IngestionCallback(BaseModel):
    source_id: str
    status: str  # 'ready' | 'failed'
    error: Optional[str] = None

class ChatRequest(BaseModel):
    query: str

class StudyPlanRequest(BaseModel):
    knowledge_level: str = "beginner"
    learning_style: str = "active"

# ==============================================================================
# 3. HELPER FUNCTIONS
# ==============================================================================

def to_object_id(id_str: str) -> ObjectId:
    """Convert string ID to ObjectId, handling both string and int inputs."""
    try:
        if isinstance(id_str, int):
            # If it's an int, convert to string first
            id_str = str(id_str)
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid ID format: {id_str}")

# ==============================================================================
# 4. INGESTION CALLBACK
# ==============================================================================

@app.post("/ai/ingestion-callback")
async def ingestion_callback(cb: IngestionCallback, db: AsyncIOMotorDatabase = Depends(get_database)):
    """Handle callback from AI service when ingestion completes."""
    resource_doc = await db.resources.find_one({"source_id": cb.source_id})
    if not resource_doc:
        raise HTTPException(status_code=404, detail="Resource not found for callback")

    update_data = {}
    if cb.status == "ready":
        update_data["ingestion_status"] = "ready"
        update_data["ingestion_error"] = None
    else:
        update_data["ingestion_status"] = "failed"
        update_data["ingestion_error"] = cb.error or "Unknown ingestion error"

    await db.resources.update_one(
        {"_id": resource_doc["_id"]},
        {"$set": update_data}
    )
    return {"ok": True}

# ==============================================================================
# 5. API ENDPOINTS - LEARNING FOLDERS
# ==============================================================================

@app.post("/folders", response_model=FolderResponse)
async def create_learning_folder(
    request: FolderCreateRequest, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Creates a new, empty learning folder.
    """
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="Folder name cannot be empty")
    
    try:
        new_folder = LearningFolder(name=request.name.strip())
        result = await db.folders.insert_one(new_folder.model_dump(by_alias=True, exclude={"id"}))
        new_folder.id = result.inserted_id
        return FolderResponse(id=str(new_folder.id), name=new_folder.name)
    except Exception as e:
        print(f"Error creating folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create folder: {str(e)}")

@app.get("/folders", response_model=List[FolderResponse])
async def get_all_folders(db: AsyncIOMotorDatabase = Depends(get_database)):
    """
    Retrieves all learning folders.
    """
    try:
        cursor = db.folders.find({})
        folders = []
        async for doc in cursor:
            folders.append(FolderResponse(id=str(doc["_id"]), name=doc["name"]))
        return folders
    except Exception as e:
        print(f"Error fetching folders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch folders: {str(e)}")

@app.get("/folders/{folder_id}", response_model=FolderDetailResponse)
async def get_folder_details(folder_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    """
    Retrieves details for a single folder, including its list of resources.
    """
    try:
        folder_oid = to_object_id(folder_id)
        folder_doc = await db.folders.find_one({"_id": folder_oid})
        if not folder_doc:
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Get resources for this folder
        cursor = db.resources.find({"folder_id": str(folder_oid)})
        resources = []
        async for doc in cursor:
            resources.append(ResourceResponse(
                id=str(doc["_id"]),
                resource_type=doc["resource_type"],
                source_id=doc["source_id"],
                folder_id=doc.get("folder_id")
            ))
        
        return FolderDetailResponse(
            id=str(folder_doc["_id"]),
            name=folder_doc["name"],
            resources=resources
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching folder details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch folder details: {str(e)}")

@app.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    """
    Deletes a folder and all its resources.
    """
    try:
        folder_oid = to_object_id(folder_id)
        folder_doc = await db.folders.find_one({"_id": folder_oid})
        if not folder_doc:
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Delete folder and all its resources
        await db.folders.delete_one({"_id": folder_oid})
        await db.resources.delete_many({"folder_id": str(folder_oid)})
        
        return {"message": "Folder deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete folder: {str(e)}")

@app.delete("/resources/{resource_id}")
async def delete_resource(resource_id: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    """
    Deletes a resource from a folder.
    """
    try:
        resource_oid = to_object_id(resource_id)
        resource_doc = await db.resources.find_one({"_id": resource_oid})
        if not resource_doc:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        await db.resources.delete_one({"_id": resource_oid})
        return {"message": "Resource deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting resource: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete resource: {str(e)}")

# ==============================================================================
# 6. API ENDPOINTS - RESOURCE MANAGEMENT & INGESTION
# ==============================================================================

@app.post("/folders/{folder_id}/add-youtube", response_model=ResourceResponse)
async def add_youtube_resource(
    folder_id: str, 
    request: YouTubeAddRequest, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Adds a YouTube video resource to a folder and triggers AI ingestion.
    (Note: This example adds the first URL. A real app might add all.)
    """
    try:
        folder_oid = to_object_id(folder_id)
        folder_doc = await db.folders.find_one({"_id": folder_oid})
        if not folder_doc:
            raise HTTPException(status_code=404, detail="Folder not found")

        if not request.urls or len(request.urls) == 0:
            raise HTTPException(status_code=400, detail="At least one URL is required")

        # 1. Call the AI service to *start* the ingestion
        success = await ai_service.trigger_youtube_ingestion(request.urls)
        if not success:
            raise HTTPException(status_code=500, detail="AI service failed to start ingestion.")

        # 2. If ingestion is triggered, add the resource(s) to our database
        # For this example, we'll just add the first URL
        url = request.urls[0]
        
        # Check if this resource already exists in this folder
        existing = await db.resources.find_one({
            "folder_id": str(folder_oid),
            "source_id": url,
            "resource_type": "youtube"
        })
        
        if existing:
            raise HTTPException(
                status_code=400, 
                detail=f"This YouTube URL already exists in this folder"
            )
        
        # Use original URL as source_id so AI service can find it
        new_resource = Resource(
            resource_type="youtube",
            source_id=url,  # Use original URL for AI compatibility
            folder_id=str(folder_oid)
        )
        result = await db.resources.insert_one(new_resource.model_dump(by_alias=True, exclude={"id"}))
        new_resource.id = result.inserted_id
        
        return ResourceResponse(
            id=str(new_resource.id),
            resource_type=new_resource.resource_type,
            source_id=new_resource.source_id,
            folder_id=new_resource.folder_id
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding YouTube resource: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add resource: {str(e)}")

@app.post("/folders/{folder_id}/upload-pdf", response_model=ResourceResponse)
async def upload_pdf_resource(
    folder_id: str, 
    file: UploadFile = File(...), 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Adds a PDF resource to a folder and triggers AI ingestion.
    """
    try:
        folder_oid = to_object_id(folder_id)
        folder_doc = await db.folders.find_one({"_id": folder_oid})
        if not folder_doc:
            raise HTTPException(status_code=404, detail="Folder not found")

        file_content = await file.read()
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")

        # Check if this resource already exists in this folder
        existing = await db.resources.find_one({
            "folder_id": str(folder_oid),
            "source_id": file.filename,
            "resource_type": "pdf"
        })
        
        if existing:
            raise HTTPException(
                status_code=400, 
                detail=f"Resource '{file.filename}' already exists in this folder"
            )

        # 1. CREATE THE RESOURCE IN DB FIRST (with pending status)
        new_resource = Resource(
            resource_type="pdf",
            source_id=file.filename,  # Use original filename for AI compatibility
            folder_id=str(folder_oid),
            ingestion_status="pending",
        )
        result = await db.resources.insert_one(new_resource.model_dump(by_alias=True, exclude={"id"}))
        new_resource.id = result.inserted_id

        # 2. PREPARE CALLBACK URL
        callback_base = os.getenv("PUBLIC_BACKEND_BASE_URL", "http://localhost:8008")
        callback_url = f"{callback_base}/ai/ingestion-callback"

        # 3. TRIGGER INGESTION (with callback)
        success = await ai_service.trigger_pdf_ingestion(file.filename, file_content, callback_url)
        
        if not success:
            # Mark as failed if trigger fails
            await db.resources.update_one(
                {"_id": new_resource.id},
                {"$set": {
                    "ingestion_status": "failed",
                    "ingestion_error": "Failed to start ingestion"
                }}
            )
            raise HTTPException(status_code=500, detail="AI service failed to start ingestion.")

        return ResourceResponse(
            id=str(new_resource.id),
            resource_type=new_resource.resource_type,
            source_id=new_resource.source_id,
            folder_id=new_resource.folder_id
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error uploading PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload resource: {str(e)}")

# ==============================================================================
# 7. API ENDPOINTS - AI TASK PROXY
# ==============================================================================

@app.post("/resources/{resource_id}/chat")
async def chat_with_resource(
    resource_id: str, 
    request: ChatRequest, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Proxies a chat request to the AI API for a specific resource.
    """
    try:
        resource_oid = to_object_id(resource_id)
        resource_doc = await db.resources.find_one({"_id": resource_oid})
        if not resource_doc:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        resource = Resource(**resource_doc)
        response = await ai_service.get_chat_response(request.query, resource.source_id)
        if not response:
            raise HTTPException(status_code=500, detail="AI service failed to respond.")
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process chat: {str(e)}")

@app.post("/resources/{resource_id}/generate-notes")
async def get_notes_for_resource(
    resource_id: str, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Proxies a notes generation request to the AI API.
    """
    try:
        resource_oid = to_object_id(resource_id)
        resource_doc = await db.resources.find_one({"_id": resource_oid})
        if not resource_doc:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        resource = Resource(**resource_doc)
        
        # 1. CHECK THE CACHE (our database column)
        if resource.generated_notes:
            print(f"Returning cached notes for resource: {resource.source_id}")
            return {"notes": resource.generated_notes}
        
        # 2. IF NOT CACHED, call the AI service
        print(f"No cache found. Generating new notes for: {resource.source_id}")
        response = await ai_service.get_generated_notes(resource.source_id)
        if not response or "notes" not in response:
            raise HTTPException(status_code=500, detail="AI service failed to generate notes.")
        
        # 3. SAVE TO CACHE
        await db.resources.update_one(
            {"_id": resource_oid},
            {"$set": {"generated_notes": response["notes"]}}
        )
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating notes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate notes: {str(e)}")

@app.post("/resources/{resource_id}/generate-study-plan")
async def get_plan_for_resource(
    resource_id: str, 
    request: StudyPlanRequest, 
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Proxies a study plan generation request to the AI API.
    """
    try:
        resource_oid = to_object_id(resource_id)
        resource_doc = await db.resources.find_one({"_id": resource_oid})
        if not resource_doc:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        resource = Resource(**resource_doc)
        response = await ai_service.get_generated_study_plan(
            resource.source_id, 
            request.knowledge_level, 
            request.learning_style
        )
        if not response:
            raise HTTPException(status_code=500, detail="AI service failed to generate study plan.")
        
        return response
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error generating study plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate study plan: {str(e)}")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Cognivia AI Backend"}

# ==============================================================================
# 8. RUN THE SERVER
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    # This server should run on a different port than the AI API
    # e.g., AI on 8000, Backend on 8008
    PORT = int(os.getenv("BACKEND_PORT", 8008))
    print(f"Starting Backend API server on http://localhost:{PORT}")
    uvicorn.run("main_api:app", host="0.0.0.0", port=PORT, reload=True)
