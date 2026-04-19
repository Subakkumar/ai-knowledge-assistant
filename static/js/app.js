let chatHistory = [];

async function loadDocuments() {
  const res = await fetch('/api/documents');
  const docs = await res.json();
  renderDocuments(docs);
  document.getElementById('doc-count-badge').textContent = docs.length;
}

async function loadStats() {
  const res = await fetch('/api/stats');
  const data = await res.json();
  document.getElementById('stat-docs').textContent = data.documents + ' docs';
  document.getElementById('stat-chunks').textContent = data.chunks + ' chunks';
}

function renderDocuments(docs) {
  const list = document.getElementById('documents-list');
  if (!docs.length) {
    list.innerHTML = '<div class="empty-docs">No documents yet</div>';
    return;
  }
  list.innerHTML = docs.map(d => `
    <div class="doc-item" id="docitem-${d.doc_id}">
      <div class="doc-info">
        <div class="doc-name" title="${d.filename}">${d.filename}</div>
        <div class="doc-meta">${d.chunk_count} chunks · ${(d.char_count/1000).toFixed(1)}k chars</div>
      </div>
      <span class="doc-type-badge ${d.file_type}">${d.file_type.toUpperCase()}</span>
      <button class="doc-delete" onclick="deleteDoc('${d.doc_id}')" title="Remove">&#x2715;</button>
    </div>
  `).join('');
}

async function uploadFile(input) {
  const file = input.files[0];
  if (!file) return;

  const statusEl = document.getElementById('upload-status');
  statusEl.className = 'upload-status loading';
  statusEl.textContent = `Uploading ${file.name}...`;
  statusEl.classList.remove('hidden');

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    const data = await res.json();

    if (!res.ok) {
      statusEl.className = 'upload-status error';
      statusEl.textContent = data.error || 'Upload failed';
      return;
    }

    statusEl.className = 'upload-status success';
    statusEl.textContent = `✓ ${data.filename} — ${data.chunks} chunks indexed`;
    await loadDocuments();
    await loadStats();

    setTimeout(() => statusEl.classList.add('hidden'), 4000);
  } catch (e) {
    statusEl.className = 'upload-status error';
    statusEl.textContent = 'Upload failed. Check server.';
  }

  input.value = '';
}

async function deleteDoc(docId) {
  if (!confirm('Remove this document from your knowledge base?')) return;
  await fetch('/api/documents/' + docId, { method: 'DELETE' });
  await loadDocuments();
  await loadStats();
}

async function sendMessage() {
  const input = document.getElementById('question-input');
  const question = input.value.trim();
  if (!question) return;

  input.value = '';
  input.style.height = 'auto';
  document.getElementById('send-btn').disabled = true;

  const messagesEl = document.getElementById('chat-messages');

  const welcomeEl = messagesEl.querySelector('.welcome-message');
  if (welcomeEl) welcomeEl.remove();

  appendMessage('user', question, [], '');

  const typingEl = document.createElement('div');
  typingEl.className = 'message assistant';
  typingEl.id = 'typing';
  typingEl.innerHTML = `
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>`;
  messagesEl.appendChild(typingEl);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, history: chatHistory })
    });
    const data = await res.json();

    document.getElementById('typing')?.remove();

    if (data.error) {
      appendMessage('assistant', 'Error: ' + data.error, [], '');
      return;
    }

    chatHistory.push({ role: 'user', content: question });
    chatHistory.push({ role: 'assistant', content: data.answer });
    if (chatHistory.length > 12) chatHistory = chatHistory.slice(-12);

    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    appendMessage('assistant', data.answer, data.sources || [], time);
  } catch (e) {
    document.getElementById('typing')?.remove();
    appendMessage('assistant', 'Network error. Make sure the server is running.', [], '');
  }

  document.getElementById('send-btn').disabled = false;
}

function appendMessage(role, content, sources, time) {
  const messagesEl = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'message ' + role;

  const timeStr = time || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  let sourcesHTML = '';
  if (sources && sources.length > 0) {
    sourcesHTML = `<div class="sources-row">${sources.map(s =>
      `<span class="source-chip">${s.filename} ${s.relevance}%</span>`
    ).join('')}</div>`;
  }

  div.innerHTML = `
    <div class="message-bubble">${escapeHtml(content)}</div>
    ${sourcesHTML}
    <div class="message-time">${timeStr}</div>
  `;

  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

async function clearChat() {
  if (!confirm('Clear chat history?')) return;
  await fetch('/api/chat/clear', { method: 'POST' });
  chatHistory = [];
  const messagesEl = document.getElementById('chat-messages');
  messagesEl.innerHTML = `
    <div class="welcome-message">
      <div class="welcome-icon">&#9679;</div>
      <h3>Your personal AI knowledge assistant</h3>
      <p>Upload documents on the left, then ask anything. I'll answer with citations from your files.</p>
      <div class="supported-formats">
        <span>PDF</span><span>TXT</span><span>Markdown</span>
      </div>
    </div>`;
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

const uploadArea = document.getElementById('upload-area');
uploadArea.addEventListener('dragover', e => { e.preventDefault(); uploadArea.classList.add('dragover'); });
uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
uploadArea.addEventListener('drop', e => {
  e.preventDefault();
  uploadArea.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) {
    const input = document.getElementById('file-input');
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    uploadFile(input);
  }
});

loadDocuments();
loadStats();