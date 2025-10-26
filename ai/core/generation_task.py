# AI/core/generation_task.py

"""
Handles long-form content generation tasks like creating synthesized notes
and personalized study plans based on the entire context of ingested documents.
"""

import os
from typing import List

# Langchain core components
from langchain.chains.llm import LLMChain
from langchain.prompts import PromptTemplate
from langchain_community.docstore.document import Document

# Import from our custom modules
# from llm_connector import get_llm
# from ingestion.common_utils import initialize_clients, create_namespace_from_url

import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from ai.ingestion.common_utils import initialize_clients, create_namespace_from_url
from ai.core.llm_connector import get_llm

# ==============================================================================
# 1. PROMPT ENGINEERING
# ==============================================================================

# Prompt for synthesizing comprehensive notes from a large body of text.
NOTES_GENERATION_PROMPT_TEMPLATE = """
CONTEXT:
{context}

INSTRUCTIONS:
- You are an expert academic assistant. Your task is to synthesize the provided CONTEXT into a clear, concise, and well-structured set of notes.
- The notes should be in Markdown format.
- Identify the main topics and create headings for each.
- Under each topic, use bullet points to list key concepts, definitions, and important facts.
- Your goal is to create a study guide that a college student can easily use for review.
- Generate the notes based ONLY on the provided CONTEXT. Do not include any external information.
"""

# Prompt for creating a personalized study plan.
# This prompt is dynamic and will be formatted with user-specific inputs.
STUDY_PLAN_PROMPT_TEMPLATE = """
CONTEXT:
{context}

INSTRUCTIONS:
- You are an expert university tutor. A student has provided you with the learning materials in the CONTEXT above.
- The student's self-assessed knowledge level is: **{knowledge_level}**.
- The student's preferred learning style is: **{learning_style}**.

- Your task is to create a personalized 5-day study plan based ONLY on the provided CONTEXT and the student's profile.
- The plan should be structured, actionable, and formatted in Markdown.
- For each day, provide:
  1. A clear "Topic Focus" for the day.
  2. A list of "Key Concepts" to master.
  3. A "Suggested Activity" that aligns with their learning style (e.g., for a 'visual' learner, suggest drawing diagrams; for an 'active' learner, suggest solving practice problems).
- Ensure the plan logically progresses from foundational topics to more advanced ones.
"""


# ==============================================================================
# 2. THE CONTENT GENERATOR CLASS
# ==============================================================================

class ContentGenerator:
    """
    Handles synthesis and generation of content from a full set of documents.
    """
    def __init__(self):
        """
        Initializes the necessary components for content generation.
        """
        print("Initializing Content Generator...")
        try:
            self.pinecone_client, self.embedding_model = initialize_clients()
            self.llm = get_llm()

            if not self.llm:
                raise ConnectionError("Failed to initialize the LLM. Is the Ollama server running?")
            
            self.pinecone_index_host = os.getenv("PINECONE_INDEX_HOST")
            if not self.pinecone_index_host:
                raise ValueError("PINECONE_INDEX_HOST is not set.")

            print("Content Generator initialized successfully.")
        except Exception as e:
            print(f"FATAL: Error during ContentGenerator initialization: {e}")
            raise

    def _get_all_documents_in_namespace(self, namespace: str) -> List[Document]:
        """
        Fetches all document chunks from a specific Pinecone namespace.
        """
        print(f"Retrieving all documents from namespace: {namespace}...")
        try:
            index = self.pinecone_client.Index(host=self.pinecone_index_host)
            # Query for a large number of vectors to get all documents.
            # Pinecone's limit per query is 1,000. This should be sufficient for most documents.
            query_response = index.query(
                namespace=namespace,
                vector=[0]*384, # A dummy vector, as we just want all docs
                top_k=1000,
                include_metadata=True
            )
            
            docs = []
            for match in query_response.get('matches', []):
                doc = Document(
                    page_content=match.get('metadata', {}).get('text', ''),
                    metadata=match.get('metadata', {})
                )
                docs.append(doc)
            
            print(f"Retrieved {len(docs)} document chunks.")
            return docs
        except Exception as e:
            print(f"Error retrieving documents from Pinecone: {e}")
            return []

    def _run_generation_chain(self, prompt_template: str, context: str, **kwargs) -> str:
        """
        A helper function to run a standard LLM generation chain.
        """
        prompt = PromptTemplate(
            template=prompt_template,
            input_variables=list(kwargs.keys()) + ["context"]
        )
        
        chain = LLMChain(llm=self.llm, prompt=prompt)
        
        input_data = {"context": context, **kwargs}
        
        print("Invoking generation chain...")
        result = chain.invoke(input_data)
        
        return result.get("text", "Sorry, I couldn't generate the content.")

    def generate_notes(self, source_url_or_filename: str) -> str:
        """
        Generates synthesized notes for a given learning folder.
        """
        namespace = create_namespace_from_url(f"file://{source_url_or_filename}" if not "://" in source_url_or_filename else source_url_or_filename)
        print(f"\n--- Starting Notes Generation for: {namespace} ---")
        
        documents = self._get_all_documents_in_namespace(namespace)
        if not documents:
            return "No content found for this source. Cannot generate notes."
            
        full_context = "\n\n---\n\n".join([doc.page_content for doc in documents])
        
        return self._run_generation_chain(NOTES_GENERATION_PROMPT_TEMPLATE, full_context)

    def generate_study_plan(self, source_url_or_filename: str, knowledge_level: str, learning_style: str) -> str:
        """
        Generates a personalized study plan for a given learning folder.
        """
        namespace = create_namespace_from_url(f"file://{source_url_or_filename}" if not "://" in source_url_or_filename else source_url_or_filename)
        print(f"\n--- Starting Study Plan Generation for: {namespace} ---")
        print(f"Profile: {knowledge_level} knowledge, {learning_style} style")

        documents = self._get_all_documents_in_namespace(namespace)
        if not documents:
            return "No content found for this source. Cannot generate a study plan."
            
        full_context = "\n\n---\n\n".join([doc.page_content for doc in documents])
        
        return self._run_generation_chain(
            STUDY_PLAN_PROMPT_TEMPLATE,
            full_context,
            knowledge_level=knowledge_level,
            learning_style=learning_style
        )

# ==============================================================================
# 3. EXAMPLE USAGE
# ==============================================================================

if __name__ == "__main__":
    TEST_SOURCE_ID = "https://www.youtube.com/watch?v=mBjPyte2pXo" 

    try:
        generator = ContentGenerator()

        # --- Test Note Generation ---
        print("\n" + "="*50)
        print("Testing Note Generation...")
        notes = generator.generate_notes(TEST_SOURCE_ID)
        print("\n--- GENERATED NOTES ---")
        print(notes)
        print("="*50)
        
        # --- Test Study Plan Generation ---
        print("\n" + "="*50)
        print("Testing Study Plan Generation...")
        study_plan = generator.generate_study_plan(
            source_url_or_filename=TEST_SOURCE_ID,
            knowledge_level="beginner",
            learning_style="visual"
        )
        print("\n--- GENERATED STUDY PLAN ---")
        print(study_plan)
        print("="*50)

    except Exception as e:
        print(f"Failed to run content generator CLI: {e}")
