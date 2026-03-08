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

    // Search
    search: (query, limit = 20) => request(`/search?q=${encodeURIComponent(query)}&limit=${limit}`),

    // Graph
    getGraph: () => request('/graph'),
    getLocalGraph: (path, depth = 1) => request(`/graph/${encodeURI(path)}?depth=${depth}`),

    // Tags
    getTags: () => request('/tags'),
    getNotesByTag: (tag) => request(`/tags/${encodeURIComponent(tag)}`),
};
