# backend/database.py

"""
MongoDB database models and connection logic for the backend.
We use Pydantic for validation and Motor for async MongoDB operations.
"""

import os
from typing import Optional, List
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()

# --- MongoDB Configuration ---
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "cognivia")

# Global MongoDB client
client: Optional[AsyncIOMotorClient] = None
database = None

# --- Helper for ObjectId conversion ---
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.json_or_python_schema(
            json_schema=core_schema.str_schema(),
            python_schema=core_schema.union_schema([
                core_schema.is_instance_schema(ObjectId),
                core_schema.chain_schema([
                    core_schema.str_schema(),
                    core_schema.no_info_plain_validator_function(cls.validate),
                ])
            ]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: str(x)
            ),
        )

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str):
            if ObjectId.is_valid(v):
                return ObjectId(v)
            raise ValueError("Invalid ObjectId string")
        raise ValueError("Invalid ObjectId type")

# --- Model Definitions (Pydantic) ---

class LearningFolder(BaseModel):
    """
    Represents a self-contained folder for a specific subject.
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    name: str

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }

class Resource(BaseModel):
    """
    Represents a single resource (PDF, YouTube video) linked to a LearningFolder.
    """
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    
    ingestion_status: str = Field(default="pending")  # 'pending' | 'ready' | 'failed'
    ingestion_error: Optional[str] = None
    
    # 'pdf' or 'youtube'
    resource_type: str
    
    # Unique identifier for AI service (filename or URL)
    source_id: str
    
    # Link back to the LearningFolder (ObjectId as string)
    folder_id: Optional[str] = None
    
    # Generated notes, study plan, etc.
    generated_notes: Optional[str] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }

# --- Database Utility Functions ---

async def init_db():
    """
    Initialize MongoDB connection. Call this on startup.
    """
    global client, database
    client = AsyncIOMotorClient(MONGODB_URL)
    database = client[MONGODB_DB_NAME]
    
    # Create indexes
    await database.folders.create_index("name")
    await database.resources.create_index("source_id", unique=True)
    await database.resources.create_index("folder_id")
    
    print(f"Connected to MongoDB: {MONGODB_DB_NAME}")

async def close_db():
    """
    Close MongoDB connection. Call this on shutdown.
    """
    global client
    if client:
        client.close()
        print("MongoDB connection closed.")

def get_database():
    """
    FastAPI dependency that provides the database instance.
    """
    return database