from langchain.chains import RetrievalQA
from langchain_core.prompts import PromptTemplate

def build_rag_chain(llm, retriever, chain_type: str = "stuff", return_source_documents: bool = True):
    prompt = PromptTemplate.from_template(
        """Based on the context provided, answer the question clearly and concisely.
If the answer is not found, say so.

Context:
{context}

Question: {question}

Answer:"""
    )
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type=chain_type,
        retriever=retriever,
        return_source_documents=return_source_documents,
        chain_type_kwargs={"prompt": prompt},
    )
