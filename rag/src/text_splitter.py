from langchain.text_splitter import RecursiveCharacterTextSplitter

def get_text_splitter(chunk_size: int, chunk_overlap: int):
    return RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
