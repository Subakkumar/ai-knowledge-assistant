# Personal AI Knowledge Assistant

A RAG (Retrieval-Augmented Generation) powered assistant that lets you chat with your own documents. Upload PDFs, text files, or markdown notes and get AI answers with exact source citations. A excellent local file reader using RAG framework. 

## Features

- Upload PDF, TXT, and Markdown documents
- Vector search using ChromaDB + sentence transformers
- Conversational chat with full context memory
- Source citations with relevance scores on every answer
- Drag and drop file upload
- Document management — add and remove from knowledge base

## Tech Stack

- **Backend**: Python, Flask, SQLAlchemy
- **Vector DB**: ChromaDB with all-MiniLM-L6-v2 embeddings
- **AI**: Groq (Llama 3.3 70B)
- **Frontend**: Vanilla HTML/CSS/JS

## Setup

1. Clone the repo
2. `python -m venv venv` then activate
3. `pip install -r requirements.txt`
4. Create `.env`:
5. `python app.py`
6. Open `http://localhost:5002`

## How it works

1. Documents are chunked into 500-word segments with 50-word overlap
2. Each chunk is embedded using sentence-transformers (all-MiniLM-L6-v2)
3. Embeddings stored in ChromaDB vector database
4. On each question, top 5 most relevant chunks are retrieved by cosine similarity
5. Retrieved chunks + question sent to Groq LLM for synthesized answer with citations
