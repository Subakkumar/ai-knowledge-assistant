import chromadb
from chromadb.utils import embedding_functions
import os
import re

CHROMA_PATH = "./chroma_store"
COLLECTION_NAME = "knowledge_base"

client = chromadb.PersistentClient(path=CHROMA_PATH)

embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

def get_collection():
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

def chunk_text(text, chunk_size=500, overlap=50):
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = ' '.join(words[i:i+chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return [c for c in chunks if len(c.strip()) > 50]

def add_document(doc_id, filename, content, file_type):
    collection = get_collection()
    chunks = chunk_text(content)
    if not chunks:
        return 0
    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"filename": filename, "doc_id": doc_id, "file_type": file_type, "chunk_index": i} for i in range(len(chunks))]
    collection.add(documents=chunks, metadatas=metadatas, ids=ids)
    return len(chunks)

def query_knowledge_base(query, n_results=5):
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []
    n_results = min(n_results, count)
    results = collection.query(query_texts=[query], n_results=n_results)
    output = []
    if results['documents'] and results['documents'][0]:
        for doc, meta, dist in zip(results['documents'][0], results['metadatas'][0], results['distances'][0]):
            output.append({
                'content': doc,
                'filename': meta.get('filename', 'Unknown'),
                'doc_id': meta.get('doc_id', ''),
                'relevance': round((1 - dist) * 100, 1)
            })
    return output

def delete_document(doc_id):
    collection = get_collection()
    results = collection.get(where={"doc_id": doc_id})
    if results['ids']:
        collection.delete(ids=results['ids'])
    return True

def get_collection_stats():
    collection = get_collection()
    return collection.count()