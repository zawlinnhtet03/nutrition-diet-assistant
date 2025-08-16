import os
from typing import Optional
from config_loader import load_config
from embedding_model import get_gemini_embeddings
from vector_store import get_chroma_vector_store
from document_loader import load_documents_from_sources
from text_splitter import get_text_splitter
from dotenv import load_dotenv


def ingest(config_path: str = os.path.join(os.path.dirname(__file__), "..", "config.yaml"), api_key: Optional[str] = None):
    # Load .env (GOOGLE_API_KEY, etc.)
    load_dotenv()
    # Set sane defaults when running standalone
    os.environ.setdefault("USER_AGENT", "NutriBench/0.1 (https://github.com/zawlinnhtet03/nutrition-diet-assistant)")
    os.environ.setdefault("CHROMA_TELEMETRY_DISABLED", "1")
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

    cfg = load_config(os.path.abspath(config_path))

    # Load documents
    sources = cfg.get("data_ingestion", {}).get("document_sources", [])
    docs = load_documents_from_sources(sources)
    if not docs:
        print("No documents found to ingest. Update data_ingestion.document_sources in config.yaml.")
        return

    # Split
    chunking = cfg["data_ingestion"]["chunking"]
    splitter = get_text_splitter(chunk_size=chunking["chunk_size"], chunk_overlap=chunking["chunk_overlap"])
    splits = splitter.split_documents(docs)
    print(f"Loaded {len(docs)} docs -> {len(splits)} chunks")

    # Embeddings and vector store
    emb = get_gemini_embeddings(model_name=cfg["gemini"]["embedding_model"], api_key=api_key)
    vs_cfg = cfg["data_ingestion"]["vector_store"]
    vs = get_chroma_vector_store(
        persist_directory=vs_cfg["persist_directory"],
        collection_name=vs_cfg["collection_name"],
        embedding_function=emb,
    )

    # Add to store
    vs.add_documents(splits)
    # Persist and report stats
    try:
        count = vs._collection.count()  # internal but useful for verification
    except Exception:
        count = None
    try:
        vs.persist()
    except Exception:
        pass
    where_db = getattr(vs, "_persist_directory", None) or vs_cfg["persist_directory"]
    print(f"Ingestion complete. Collection count: {count if count is not None else 'unknown'}. DB: {where_db}")


if __name__ == "__main__":
    ingest()
