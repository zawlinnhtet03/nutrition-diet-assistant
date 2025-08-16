import os
from typing import List, Dict, Any
from langchain_community.document_loaders import PyPDFLoader, CSVLoader, DirectoryLoader, TextLoader, WebBaseLoader

def load_documents_from_sources(sources_config: List[Dict[str, Any]]):
    docs = []
    for source in sources_config:
        stype = source.get("type")
        if stype == "pdf" and (p := source.get("path")):
            if os.path.isdir(p):
                docs.extend(DirectoryLoader(p, glob="*.pdf", loader_cls=PyPDFLoader).load())
            elif os.path.isfile(p):
                docs.extend(PyPDFLoader(p).load())
        elif stype == "csv" and (p := source.get("path")) and os.path.isfile(p):
            docs.extend(CSVLoader(file_path=p, encoding="utf-8").load())
        elif stype == "text" and (p := source.get("path")):
            if os.path.isdir(p):
                docs.extend(DirectoryLoader(p, glob="*.txt", loader_cls=TextLoader).load())
            elif os.path.isfile(p):
                docs.extend(TextLoader(p).load())
        elif stype == "website" and (urls := source.get("urls")):
            docs.extend(WebBaseLoader(web_paths=urls).load())
    return docs
