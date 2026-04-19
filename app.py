from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq
from werkzeug.utils import secure_filename
import os
import json

from knowledge_base import add_document, query_knowledge_base, delete_document, get_collection_stats
from document_processor import process_file

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///knowledge.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)
client = Groq(api_key=os.getenv('GROQ_API_KEY'))

class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    doc_id = db.Column(db.String(100), unique=True, nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    file_type = db.Column(db.String(20))
    chunk_count = db.Column(db.Integer, default=0)
    char_count = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'doc_id': self.doc_id,
            'filename': self.filename,
            'file_type': self.file_type,
            'chunk_count': self.chunk_count,
            'char_count': self.char_count,
            'uploaded_at': self.uploaded_at.strftime('%Y-%m-%d %H:%M')
        }

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(10))
    content = db.Column(db.Text)
    sources = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'content': self.content,
            'sources': json.loads(self.sources),
            'created_at': self.created_at.strftime('%H:%M')
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_document():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No file selected'}), 400

    filename = secure_filename(file.filename)

    try:
        text, file_type = process_file(file, filename)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    if len(text) < 50:
        return jsonify({'error': 'File appears to be empty or unreadable'}), 400

    doc_id = f"doc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename[:20]}"

    existing = Document.query.filter_by(filename=filename).first()
    if existing:
        delete_document(existing.doc_id)
        db.session.delete(existing)
        db.session.commit()

    chunk_count = add_document(doc_id, filename, text, file_type)

    doc = Document(
        doc_id=doc_id,
        filename=filename,
        file_type=file_type,
        chunk_count=chunk_count,
        char_count=len(text)
    )
    db.session.add(doc)
    db.session.commit()

    return jsonify({
        'success': True,
        'filename': filename,
        'chunks': chunk_count,
        'characters': len(text),
        'doc_id': doc_id
    })

@app.route('/api/documents')
def list_documents():
    docs = Document.query.order_by(Document.uploaded_at.desc()).all()
    return jsonify([d.to_dict() for d in docs])

@app.route('/api/documents/<doc_id>', methods=['DELETE'])
def remove_document(doc_id):
    doc = Document.query.filter_by(doc_id=doc_id).first_or_404()
    delete_document(doc_id)
    db.session.delete(doc)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    question = data.get('question', '').strip()
    chat_history = data.get('history', [])

    if not question:
        return jsonify({'error': 'No question provided'}), 400

    stats = get_collection_stats()
    if stats == 0:
        return jsonify({
            'answer': "Your knowledge base is empty. Please upload some documents first — PDFs, text files, or markdown notes.",
            'sources': []
        })

    relevant_chunks = query_knowledge_base(question, n_results=5)

    if not relevant_chunks:
        return jsonify({
            'answer': "I couldn't find relevant information in your knowledge base for that question.",
            'sources': []
        })

    context = "\n\n".join([
        f"[Source: {chunk['filename']} | Relevance: {chunk['relevance']}%]\n{chunk['content']}"
        for chunk in relevant_chunks
    ])

    history_text = ""
    if chat_history:
        recent = chat_history[-6:]
        history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in recent])

    system_prompt = """You are a personal knowledge assistant. You answer questions based ONLY on the provided context from the user's documents.

Rules:
- Always cite which document your answer comes from using (Source: filename)
- If the context doesn't contain enough information, say so clearly
- Synthesize across multiple sources when relevant
- Be conversational but precise
- Never make up information not in the context"""

    user_prompt = f"""Context from knowledge base:
{context}

{"Recent conversation:" + history_text if history_text else ""}

Question: {question}

Answer based on the context above, with source citations:"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=1000
    )

    answer = response.choices[0].message.content.strip()

    user_msg = ChatMessage(role='user', content=question, sources='[]')
    ai_msg = ChatMessage(
        role='assistant',
        content=answer,
        sources=json.dumps([{'filename': c['filename'], 'relevance': c['relevance']} for c in relevant_chunks[:3]])
    )
    db.session.add(user_msg)
    db.session.add(ai_msg)
    db.session.commit()

    return jsonify({
        'answer': answer,
        'sources': [{'filename': c['filename'], 'relevance': c['relevance']} for c in relevant_chunks[:3]]
    })

@app.route('/api/chat/history')
def chat_history():
    messages = ChatMessage.query.order_by(ChatMessage.created_at.desc()).limit(50).all()
    messages.reverse()
    return jsonify([m.to_dict() for m in messages])

@app.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    ChatMessage.query.delete()
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/stats')
def stats():
    doc_count = Document.query.count()
    chunk_count = get_collection_stats()
    msg_count = ChatMessage.query.count()
    return jsonify({
        'documents': doc_count,
        'chunks': chunk_count,
        'messages': msg_count
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5002)