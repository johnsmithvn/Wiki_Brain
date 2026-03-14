// ============================================
// API Client - Second Brain
// ============================================

const BASE = '/api';

async function request(path, options = {}) {
    const url = `${BASE}${path}`;
    const config = {
        headers: { 'Content-Type': 'application/json', ...options.headers },
        ...options,
    };
    const res = await fetch(url, config);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }
    if (res.status === 204) return null;
    return res.json();
}

export const api = {
    // Notes
    getTree: () => request('/notes/tree'),
    listNotes: () => request('/notes/list'),
    getNote: (path) => request(`/notes/${encodeURI(path)}`),
    getNoteMeta: (path) => request(`/notes/${encodeURI(path)}/meta`),
    createNote: (path, content = '') => request('/notes', {
        method: 'POST',
        body: JSON.stringify({ path, content }),
    }),
    updateNote: (path, content) => request(`/notes/${encodeURI(path)}`, {
        method: 'PUT',
        body: JSON.stringify({ content }),
    }),
    deleteNote: (path) => request(`/notes/${encodeURI(path)}`, { method: 'DELETE' }),
    renameNote: (path, newPath) => request(`/notes/${encodeURI(path)}/rename`, {
        method: 'PATCH',
        body: JSON.stringify({ new_path: newPath }),
    }),
    createFolder: (path) => request('/notes/folder', {
        method: 'POST',
        body: JSON.stringify({ path }),
    }),
    renameFolder: (oldPath, newPath) => request('/notes/folder-rename', {
        method: 'PATCH',
        body: JSON.stringify({ old_path: oldPath, new_path: newPath }),
    }),

    // Search
    search: (query, limit = 20, mode = 'hybrid') =>
        request(`/search?q=${encodeURIComponent(query)}&limit=${limit}&mode=${encodeURIComponent(mode)}`),

    // Graph
    getGraph: (filters = {}) => {
        const params = new URLSearchParams();
        if (filters.tags?.length) filters.tags.forEach(t => params.append('tags', t));
        if (filters.folders?.length) filters.folders.forEach(f => params.append('folders', f));
        if (filters.depth > 0) params.set('depth', String(filters.depth));
        const qs = params.toString();
        return request(`/graph${qs ? '?' + qs : ''}`);
    },
    getLocalGraph: (path, depth = 1) => request(`/graph/${encodeURI(path)}?depth=${depth}`),

    // Tags
    getTags: () => request('/tags'),
    getNotesByTag: (tag) => request(`/tags/${encodeURIComponent(tag)}`),

    // Daily
    getDailyToday: () => request('/daily/today'),
    listDailyNotes: () => request('/daily/list'),

    // Templates
    getTemplates: (folder = 'template') => request(`/templates?folder=${encodeURIComponent(folder)}`),
    getTemplate: (path) => request(`/templates/${encodeURI(path)}`),

    // Assets
    uploadImage: async (file) => {
        const form = new FormData();
        form.append('file', file);
        const res = await fetch(`${BASE}/assets/upload`, { method: 'POST', body: form });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return res.json();
    },

    // Capture
    capture: (content, source = 'manual', url = null) => {
        const body = { content, source };
        if (url) body.url = url;
        return request('/capture', { method: 'POST', body: JSON.stringify(body) });
    },

    // Inbox
    getInboxDates: () => request('/inbox'),
    getInboxEntries: (date) => request(`/inbox/${encodeURIComponent(date)}`),
    convertEntry: (date, entryId, title, folder = '', tags = []) =>
        request(`/inbox/${encodeURIComponent(date)}/${encodeURIComponent(entryId)}/convert`, {
            method: 'POST',
            body: JSON.stringify({ title, folder, tags }),
        }),
    deleteEntry: (date, entryId) =>
        request(`/inbox/${encodeURIComponent(date)}/${encodeURIComponent(entryId)}`, {
            method: 'DELETE',
        }),
    archiveEntry: (date, entryId) =>
        request(`/inbox/${encodeURIComponent(date)}/${encodeURIComponent(entryId)}/archive`, {
            method: 'POST',
        }),

    // Related Notes
    getRelatedNotes: (path, limit = 5) =>
        request(`/notes/${encodeURI(path)}/related?limit=${limit}`),

    // Chat (Phase 4)
    chatStream: (question, mode = 'chat') => {
        return fetch(`${BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question, mode }),
        });
    },
    summarizeStream: (notePath) => {
        return fetch(`${BASE}/chat/summarize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note_path: notePath }),
        });
    },
    suggestLinks: (notePath, content) =>
        request('/chat/suggest-links', {
            method: 'POST',
            body: JSON.stringify({ note_path: notePath, content }),
        }),
};
