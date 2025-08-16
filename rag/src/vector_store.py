import os
from langchain_chroma import Chroma
from chromadb.config import Settings

def get_chroma_vector_store(persist_directory: str, collection_name: str, embedding_function):
    # Normalize persist directory to absolute path (relative to project root)
    if not os.path.isabs(persist_directory):
        # Project root = two levels up from this file (rag/src -> project)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        persist_directory = os.path.abspath(os.path.join(project_root, persist_directory))
    os.makedirs(persist_directory, exist_ok=True)
    client_settings = Settings(anonymized_telemetry=False)
    return Chroma(
        persist_directory=persist_directory,
        collection_name=collection_name,
        embedding_function=embedding_function,
        client_settings=client_settings,
    )
