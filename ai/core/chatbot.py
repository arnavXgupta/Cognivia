# AI/core/chatbot.py

"""
The core component for the Retrieval-Augmented Generation (RAG) chatbot.

This module brings together the vector database, embedding models, and the LLM
to provide context-aware answers to user queries based on ingested documents.
"""

import os
from typing import Dict, Any, List

# Langchain core components
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain_pinecone import Pinecone as LangChainPinecone
from langchain_community.docstore.document import Document

# Import from our custom modules
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from ai.ingestion.common_utils import initialize_clients, create_namespace_from_url
from ai.core.llm_connector import get_llm

# --- CONSTANTS AND CONFIGURATION ---
# Number of relevant document chunks to retrieve for context
PINECONE_TOP_K = 4

# ==============================================================================
# 1. PROMPT ENGINEERING
# ==============================================================================

# This prompt template is crucial for guiding the LLM's behavior.
# It explicitly tells the model to use ONLY the provided context, which prevents
# it from hallucinating or using its general knowledge.
RAG_PROMPT_TEMPLATE = """
CONTEXT:
{context}

QUERY:
{question}

INSTRUCTIONS:
- You are a helpful AI assistant for a college student.
- Your task is to answer the user's QUERY based ONLY on the provided CONTEXT.
- If the CONTEXT does not contain the answer, you MUST state that the information is not available in the provided documents. Do NOT use any external knowledge.
- Your answer should be concise, clear, and directly address the user's question.
- Cite the source of your information where possible, using the metadata from the context.
"""

# ==============================================================================
# 2. THE CONTEXTUAL CHATBOT CLASS
# ==============================================================================

class ContextualChatbot:
    """
    A chatbot that uses a vector store to answer questions in a context-aware manner.
    """
    def __init__(self, llm, embedding_model, pinecone_client):
        """
        Initializes all necessary components for the RAG pipeline upon creation.
        """
        print("Initializing Contextual Chatbot...")
        try:
            # self.pinecone_client, self.embedding_model = initialize_clients()
            # self.llm = get_llm()
            self.llm = llm
            self.embedding_model = embedding_model
            self.pinecone_client = pinecone_client
            
            if not self.llm:
                raise ConnectionError("Failed to initialize the LLM. Is the Ollama server running?")

            self.pinecone_index_name = os.getenv("PINECONE_INDEX_NAME")
            if not self.pinecone_index_name:
                raise ValueError("PINECONE_INDEX_NAME is not set in environment variables.")

            print("Chatbot initialized successfully.")
        except Exception as e:
            print(f"FATAL: Error during chatbot initialization: {e}")
            # In a real app, you might want to handle this more gracefully
            # For now, we'll re-raise to stop execution if setup fails.
            raise

    def _get_retriever(self, namespace: str):
        """
        Creates a LangChain retriever for a specific Pinecone namespace.
        """
        print(f"Connecting to vector store for namespace: {namespace}...")
        vector_store = LangChainPinecone.from_existing_index(
            index_name=self.pinecone_index_name,
            embedding=self.embedding_model,
            namespace=namespace
        )
        
        # The retriever is the component that fetches documents from the vector store.
        # 'k' determines how many documents to retrieve.
        return vector_store.as_retriever(search_kwargs={"k": PINECONE_TOP_K})

    def ask(self, query: str, source_url_or_filename: str) -> Dict[str, Any]:
        """
        Asks a question to the RAG pipeline and gets a context-aware answer.

        Args:
            query: The user's question.
            source_url_or_filename: The unique identifier for the learning folder
                                    (e.g., the URL or filename of an ingested doc).

        Returns:
            A dictionary containing the answer and the source documents.
        """
        if not query:
            return {"answer": "Please provide a question.", "sources": []}

        # Each "learning folder" corresponds to a unique namespace in Pinecone.
        namespace = create_namespace_from_url(f"file://{source_url_or_filename}" if not "://" in source_url_or_filename else source_url_or_filename)
        
        print(f"\n--- New Query ---")
        print(f"Question: {query}")
        print(f"Target Namespace: {namespace}")
        
        try:
            retriever = self._get_retriever(namespace)
            
            # Create a custom prompt
            prompt = PromptTemplate(
                template=RAG_PROMPT_TEMPLATE,
                input_variables=["context", "question"]
            )

            # Create the RetrievalQA chain
            # This chain automates the entire RAG process.
            qa_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",  # "stuff" means all retrieved docs are "stuffed" into the prompt
                retriever=retriever,
                return_source_documents=True,
                chain_type_kwargs={"prompt": prompt}
            )

            print("Invoking RAG chain...")
            result = qa_chain.invoke({"query": query})

            # Format the sources for a clean output
            sources = [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                } for doc in result.get("source_documents", [])
            ]

            return {
                "answer": result.get("result", "Sorry, I couldn't process the query."),
                "sources": sources
            }

        except Exception as e:
            print(f"An error occurred during the RAG chain execution: {e}")
            return {"answer": "An error occurred while processing your request.", "sources": []}

# ==============================================================================
# 3. EXAMPLE USAGE
# ==============================================================================

# if __name__ == "__main__":
#     # This block allows you to test the chatbot directly from the command line.
    
#     # --- IMPORTANT ---
#     # Replace this with a URL or filename that you have ALREADY INGESTED.
#     # The namespace will be derived from this.
#     # TEST_SOURCE_ID = "https://www.youtube.com/watch?v=mBjPyte2pXo" 
#     TEST_SOURCE_ID = "OS.pdf"
#     # Or for a PDF: TEST_SOURCE_ID = "my_document.pdf"
    
#     try:
#         chatbot = ContextualChatbot()

#         # Start a simple interactive loop
#         print("\n--- Contextual Chatbot CLI ---")
#         print(f"Targeting knowledge from: {TEST_SOURCE_ID}")
#         print("Type 'exit' to quit.")
        
#         while True:
#             user_query = input("\nYour Question: ")
#             if user_query.lower() == 'exit':
#                 break
            
#             response = chatbot.ask(user_query, TEST_SOURCE_ID)

#             print("\n--- AI Answer ---")
#             print(response["answer"])
#             print("\n--- Sources Used ---")
#             if response["sources"]:
#                 for i, source in enumerate(response["sources"]):
#                     print(f"  Source {i+1}:")
#                     print(f"    - Content: '{source['content'][:100]}...'")
#                     print(f"    - Metadata: {source['metadata']}")
#             else:
#                 print("  No sources were retrieved for this query.")
#             print("--------------------\n")

#     except Exception as e:
#         print(f"Failed to run chatbot CLI: {e}")
