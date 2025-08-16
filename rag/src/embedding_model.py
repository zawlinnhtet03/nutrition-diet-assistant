from typing import Optional
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import os

def get_gemini_embeddings(model_name: str = "models/embedding-001", api_key: Optional[str] = None):
    """
    Returns a Gemini embeddings model via LangChain.
    """
    key = api_key or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY is not set.")
    emb = GoogleGenerativeAIEmbeddings(model=model_name, google_api_key=key)
    return emb
