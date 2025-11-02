# backend/database.py

"""
This file defines the database models and connection logic for the backend.
We use SQLModel, which combines SQLAlchemy (for the database) and Pydantic (for data validation).
"""

from typing import Optional, List
from sqlmodel import Field, SQLModel, create_engine, Session, Relationship

# --- Configuration ---

# We'll use SQLite, which stores the database in a single file named 'backend.db'
# This is perfect for development.
SQLITE_FILE_NAME = "backend.db"
sqlite_url = f"sqlite:///{SQLITE_FILE_NAME}"

# The engine is the one object that manages connections to the database.
engine = create_engine(sqlite_url, echo=True)

# --- Model Definitions ---
# These are the "tables" in our database.

class LearningFolder(SQLModel, table=True):
    """
    Represents a self-contained folder for a specific subject.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    # user_id: int = Field(foreign_key="user.id") # We'll add this when we add users

    # A folder can have many resources
    resources: List["Resource"] = Relationship(back_populates="folder")


class Resource(SQLModel, table=True):
    """
    Represents a single resource (PDF, YouTube video) linked to a LearningFolder.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # 'pdf' or 'youtube'
    resource_type: str 
    
    # This will be the unique ID we use to talk to the AI API
    # e.g., "my_document.pdf" or "https://www.youtube.com/watch?v=..."
    # Note: Not unique globally - same file/URL can be in different folders
    # The AI service uses this to identify the namespace in Pinecone
    source_id: str = Field(index=True) 
    
    # Link back to the LearningFolder
    folder_id: Optional[int] = Field(default=None, foreign_key="learningfolder.id", index=True)
    folder: Optional[LearningFolder] = Relationship(back_populates="resources")
    
    # Note: We handle uniqueness at the application level (checking for duplicates before insert)
    # This avoids SQLModel/SQLAlchemy compatibility issues with composite unique constraints


# --- Database Utility Functions ---

def create_db_and_tables():
    """
    Call this function once (e.g., in main_api.py on startup)
    to create the database file and all the tables.
    """
    print("Creating database and tables...")
    SQLModel.metadata.create_all(engine)
    print("Database and tables created successfully.")

def get_session():
    """
    A FastAPI dependency that provides a database session for each request.
    This ensures that each request has its own isolated database connection.
    """
    with Session(engine) as session:
        yield session
