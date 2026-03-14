// ============================================
// Chat Module - Second Brain (Phase 4)
// ============================================

import { api } from './api.js';

let chatPanel, chatMessages, chatInput, chatSendBtn, chatModeSelect;
let isStreaming = false;
let onSourceClick = null;

export function initChat({ onSelect }) {
    onSourceClick = onSelect;
    chatPanel = document.getElementById('chat-panel');
    chatMessages = document.getElementById('chat-messages');
    chatInput = document.getElementById('chat-input');
    chatSendBtn = document.getElementById('chat-send-btn');
    chatModeSelect = document.getElementById('chat-mode-select');

    if (!chatPanel) return;

    chatSendBtn.addEventListener('click', handleSend);
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
    });
}

export function openChat() {
    if (chatPanel) chatPanel.classList.add('active');
}

export function closeChat() {
    if (chatPanel) chatPanel.classList.remove('active');
}

export function toggleChat() {
    if (chatPanel) chatPanel.classList.toggle('active');
}

async function handleSend() {
    if (isStreaming || !chatInput) return;

    const question = chatInput.value.trim();
    if (!question) return;

    const mode = chatModeSelect?.value || 'chat';
    chatInput.value = '';
    chatInput.style.height = 'auto';

    // Remove empty state if present
    const emptyState = chatMessages.querySelector('.chat-empty');
    if (emptyState) emptyState.remove();

    // Add user message
    appendMessage('user', question);

    if (mode === 'chat') {
        await streamChat(question);
    } else if (mode === 'summary') {
        appendMessage('system', 'Summary mode: paste a note path to summarize');
        await streamSummary(question);
    } else if (mode === 'suggest-links') {
        await fetchSuggestLinks(question);
    }
}

async function streamChat(question) {
    isStreaming = true;
    chatSendBtn.disabled = true;

    const msgEl = appendMessage('assistant', '');
    const contentEl = msgEl.querySelector('.chat-msg-content');
    contentEl.innerHTML = '<span class="chat-typing"></span>';

    try {
        const response = await api.chatStream(question);
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            contentEl.textContent = `Error: ${err.detail || 'Chat unavailable'}`;
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;

                try {
                    const data = JSON.parse(jsonStr);

                    if (data.error) {
                        contentEl.textContent = fullText + `\n\n[Error: ${data.error}]`;
                        return;
                    }

                    if (data.token) {
                        fullText += data.token;
                        contentEl.textContent = fullText;
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }

                    if (data.done && data.sources) {
                        renderSources(msgEl, data.sources);
                    }
                } catch {
                    // skip malformed JSON
                }
            }
        }

        if (!fullText) {
            contentEl.textContent = 'No response received.';
        }
    } catch (err) {
        contentEl.textContent = `Error: ${err.message}`;
    } finally {
        isStreaming = false;
        chatSendBtn.disabled = false;
        chatInput.focus();
    }
}

async function streamSummary(notePath) {
    isStreaming = true;
    chatSendBtn.disabled = true;

    const msgEl = appendMessage('assistant', '');
    const contentEl = msgEl.querySelector('.chat-msg-content');
    contentEl.innerHTML = '<span class="chat-typing"></span>';

    try {
        const response = await api.summarizeStream(notePath);
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: response.statusText }));
            contentEl.textContent = `Error: ${err.detail || 'Summary unavailable'}`;
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullText = '';
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;

                try {
                    const data = JSON.parse(jsonStr);
                    if (data.token) {
                        fullText += data.token;
                        contentEl.textContent = fullText;
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                } catch {
                    // skip
                }
            }
        }

        if (!fullText) {
            contentEl.textContent = 'No summary generated.';
        }
    } catch (err) {
        contentEl.textContent = `Error: ${err.message}`;
    } finally {
        isStreaming = false;
        chatSendBtn.disabled = false;
        chatInput.focus();
    }
}

async function fetchSuggestLinks(content) {
    const msgEl = appendMessage('assistant', '');
    const contentEl = msgEl.querySelector('.chat-msg-content');
    contentEl.textContent = 'Finding related notes...';

    try {
        // Use content as note_path if it looks like a path, otherwise as content
        const isPath = content.endsWith('.md');
        const result = isPath
            ? await api.suggestLinks(content, '')
            : await api.suggestLinks('', content);

        if (!result.suggestions?.length) {
            contentEl.textContent = 'No link suggestions found.';
            return;
        }

        contentEl.innerHTML = '';
        const wrapper = document.createElement('div');
        wrapper.textContent = 'Suggested links:';
        wrapper.style.marginBottom = '8px';
        contentEl.appendChild(wrapper);

        const list = document.createElement('div');
        list.className = 'chat-suggestions';
        for (const s of result.suggestions) {
            const item = document.createElement('div');
            item.className = 'chat-suggestion-item';
            item.textContent = `[[${s.title || s.path}]]`;
            item.addEventListener('click', () => {
                if (onSourceClick) onSourceClick(s.path);
            });
            list.appendChild(item);
        }
        contentEl.appendChild(list);
    } catch (err) {
        contentEl.textContent = `Error: ${err.message}`;
    }
}

function appendMessage(role, text) {
    const el = document.createElement('div');
    el.className = `chat-message ${role}`;

    if (role === 'system') {
        el.textContent = text;
    } else {
        const contentEl = document.createElement('div');
        contentEl.className = 'chat-msg-content';
        contentEl.textContent = text;
        el.appendChild(contentEl);
    }

    chatMessages.appendChild(el);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return el;
}

function renderSources(msgEl, sources) {
    if (!sources?.length) return;

    const sourcesEl = document.createElement('div');
    sourcesEl.className = 'chat-sources';
    sourcesEl.textContent = 'Sources: ';

    sources.forEach((src, i) => {
        const link = document.createElement('a');
        link.textContent = src.replace('.md', '').split('/').pop();
        link.title = src;
        link.addEventListener('click', (e) => {
            e.preventDefault();
            if (onSourceClick) onSourceClick(src);
        });
        sourcesEl.appendChild(link);
        if (i < sources.length - 1) {
            sourcesEl.appendChild(document.createTextNode(', '));
        }
    });

    msgEl.appendChild(sourcesEl);
}
