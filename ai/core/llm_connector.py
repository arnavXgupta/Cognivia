# AI/core/llm_connector.py

"""
Handles the connection and configuration for the local Large Language Model
served via Ollama.

This module provides a centralized, configurable, and reliable way for the rest of
the application to get an LLM instance to work with.
"""

import os
import requests
from dotenv import load_dotenv

# Langchain's integration with Ollama
from langchain_ollama import OllamaLLM

# --- CONFIGURATION ---
load_dotenv()

# Load Ollama configuration from environment variables for flexibility
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct") # Default to 'mistral'
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", 0.2))
OLLAMA_CONTEXT_WINDOW = int(os.getenv("OLLAMA_CONTEXT_WINDOW", 131072))
OLLAMA_REQUEST_TIMEOUT = int(os.getenv("OLLAMA_REQUEST_TIMEOUT", 120))

# Global variable to hold the LLM instance (Singleton pattern)
_llm_instance = None

# ==============================================================================
# 1. CORE LLM INITIALIZATION AND HEALTH CHECK
# ==============================================================================

def _check_ollama_server_health() -> bool:
    """
    Checks if the Ollama server is running and accessible.
    """
    try:
        print(f"Checking Ollama server health at {OLLAMA_BASE_URL}...")
        response = requests.get(OLLAMA_BASE_URL, timeout=5)
        response.raise_for_status()  # Will raise an exception for 4xx/5xx status codes
        print("Ollama server is running.")
        return True
    except requests.exceptions.RequestException as e:
        print("\n" + "="*50)
        print("!!! OLLAMA SERVER NOT REACHABLE !!!")
        print(f"Error: Could not connect to Ollama server at {OLLAMA_BASE_URL}.")
        print("Please ensure the Ollama application is running and the OLLAMA_BASE_URL is correct in your .env file.")
        print(f"Details: {e}")
        print("="*50 + "\n")
        return False

def get_llm() -> OllamaLLM | None:
    """
    Initializes and returns a singleton instance of the Ollama LLM.

    This function ensures that the LLM is initialized only once and that the
    Ollama server is available before attempting to create an instance.

    Returns:
        An instance of langchain_community.llms.Ollama, or None if the server
        is not available.
    """
    global _llm_instance

    if _llm_instance is None:
        if not _check_ollama_server_health():
            # Return None to allow calling code to handle the error gracefully
            return None

        print("Initializing connection to local Ollama model...")
        try:
            _llm_instance = OllamaLLM(
                base_url=OLLAMA_BASE_URL,
                model=OLLAMA_MODEL,
                temperature=OLLAMA_TEMPERATURE,
                num_ctx=OLLAMA_CONTEXT_WINDOW,
                tfs_z=0.9, # Another parameter to control generation quality
                top_k=40,    # Top-k sampling
                top_p=0.9,   # Nucleus sampling
                request_timeout=OLLAMA_REQUEST_TIMEOUT
            )
            print("-" * 50)
            print("Ollama LLM Connector Initialized Successfully:")
            print(f"  - Model: {OLLAMA_MODEL}")
            print(f"  - Temperature: {OLLAMA_TEMPERATURE}")
            print(f"  - Context Window: {OLLAMA_CONTEXT_WINDOW}")
            print("-" * 50)

        except Exception as e:
            print(f"Failed to initialize Ollama instance: {e}")
            return None
            
    return _llm_instance

# ==============================================================================
# 2. EXAMPLE USAGE
# ==============================================================================

if __name__ == "__main__":
    print("Running LLM Connector test...")
    llm = get_llm()

    if llm:
        print("\nSuccessfully obtained LLM instance. Sending a test prompt...")
        try:
            # The .invoke() method sends a single prompt to the LLM
            response = llm.invoke("Why is the sky blue?")
            print("\n--- TEST RESPONSE ---")
            print(response)
            print("---------------------\n")
            print("Test successful. The LLM connector is working correctly.")
        except Exception as e:
            print(f"An error occurred while invoking the LLM: {e}")
    else:
        print("\nFailed to obtain LLM instance. Please check the errors above.")
