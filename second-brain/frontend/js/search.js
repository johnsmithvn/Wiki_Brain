// ============================================
// Search + Command Palette
// ============================================

import { api } from './api.js';

let onResultSelect = null;
let debounceTimer = null;
let searchMode = 'hybrid';

export function initSearch({ onSelect }) {
    onResultSelect = onSelect;

    const modal = document.getElementById('search-modal');
    const input = document.getElementById('search-input');
    const results = document.getElementById('search-results');

    // Open search
    document.getElementById('btn-open-search').addEventListener('click', openSearch);

    // Search mode toggle
    document.querySelectorAll('.search-mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            searchMode = btn.dataset.mode;
            document.querySelectorAll('.search-mode-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // Re-run search with new mode if there's a query
            const q = input.value.trim();
            if (q && !q.startsWith('/') && !q.startsWith('#')) {
                performSearch(q);
            }
        });
    });

    // Input handler with debounce
    input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const q = input.value;
        if (q.startsWith('/')) {
            showCommands(q.substring(1));
        } else {
            debounceTimer = setTimeout(() => performSearch(q), 250);
        }
    });

    // Close on Escape or click outside
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeSearch();
        if (e.key === 'Enter') {
            const selected = results.querySelector('.search-result-item.selected') || results.querySelector('.search-result-item');
            if (selected) selected.click();
        }
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            navigateResults(e.key === 'ArrowDown' ? 1 : -1);
        }
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeSearch();
    });
}

export function openSearch() {
    const modal = document.getElementById('search-modal');
    const input = document.getElementById('search-input');
    modal.classList.remove('hidden');
    input.value = '';
    input.focus();
    showDefaultView();
}

export function closeSearch() {
    document.getElementById('search-modal').classList.add('hidden');
}

function showDefaultView() {
    const results = document.getElementById('search-results');
    // Show recent notes + hint
    const recent = JSON.parse(localStorage.getItem('sb-recent') || '[]');

    let html = '';
    if (recent.length) {
        html += `<div style="padding:var(--sp-2) var(--sp-4);font-size:var(--text-xs);color:var(--text-muted);text-transform:uppercase;font-weight:600">Recent</div>`;
        html += recent.slice(0, 5).map((r, i) => `
            <div class="search-result-item${i === 0 ? ' selected' : ''}" data-path="${escapeHtml(r.path)}">
                <div class="search-result-title">${escapeHtml(r.title || r.path)}</div>
                <div class="search-result-path">${escapeHtml(r.path)}</div>
            </div>
        `).join('');
    }

    html += `
        <div style="padding:var(--sp-2) var(--sp-4);font-size:var(--text-xs);color:var(--text-muted)">
            Type to search · <kbd style="background:var(--bg-elevated);padding:1px 4px;border-radius:2px;font-size:10px">/</kbd> for commands
        </div>
    `;

    results.innerHTML = html;
    attachResultListeners(results);
}

const COMMANDS = [
    { key: 'new', label: 'Create New Note', icon: 'file-plus', action: () => document.getElementById('btn-new-note').click() },
    { key: 'daily', label: 'Open Daily Note', icon: 'calendar', action: () => document.getElementById('btn-daily-note')?.click() },
    { key: 'graph', label: 'Toggle Graph View', icon: 'git-branch', action: null },
    { key: 'capture', label: 'Quick Capture', icon: 'zap', action: null },
    { key: 'tags', label: 'Show All Tags', icon: 'hash', action: null },
];

function showCommands(filter) {
    const results = document.getElementById('search-results');
    const filtered = COMMANDS.filter(c =>
        !filter || c.key.includes(filter.toLowerCase()) || c.label.toLowerCase().includes(filter.toLowerCase())
    );

    if (!filtered.length) {
        results.innerHTML = `<div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);font-size:var(--text-sm)">No commands found</div>`;
        return;
    }

    results.innerHTML = `
        <div style="padding:var(--sp-2) var(--sp-4);font-size:var(--text-xs);color:var(--text-muted);text-transform:uppercase;font-weight:600">Commands</div>
        ${filtered.map((c, i) => `
            <div class="search-result-item${i === 0 ? ' selected' : ''}" data-command="${c.key}">
                <div class="search-result-title">
                    <i data-lucide="${c.icon}" style="width:14px;height:14px;margin-right:var(--sp-2);opacity:0.6"></i>
                    ${escapeHtml(c.label)}
                </div>
            </div>
        `).join('')}
    `;

    if (typeof lucide !== 'undefined') lucide.createIcons();

    results.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('click', () => {
            const cmd = COMMANDS.find(c => c.key === item.dataset.command);
            if (cmd?.action) { closeSearch(); cmd.action(); }
        });
        item.addEventListener('mouseenter', () => {
            results.querySelectorAll('.search-result-item').forEach(el => el.classList.remove('selected'));
            item.classList.add('selected');
        });
    });
}

async function performSearch(query) {
    const results = document.getElementById('search-results');
    const trimmed = query.trim();
    if (!trimmed) {
        showDefaultView();
        return;
    }

    if (trimmed.startsWith('#')) {
        await performTagSearch(trimmed, results);
        return;
    }

    try {
        const data = await api.search(trimmed, 20, searchMode);
        if (!data.results.length) {
            results.innerHTML = `
                <div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);font-size:var(--text-sm)">
                    No results for "${escapeHtml(trimmed)}"
                </div>
            `;
            return;
        }

        results.innerHTML = data.results.map((r, i) => `
            <div class="search-result-item${i === 0 ? ' selected' : ''}" data-path="${escapeHtml(r.path)}">
                <div class="search-result-title">${escapeHtml(r.title)}</div>
                <div class="search-result-path">${escapeHtml(r.path)}</div>
                ${r.snippet ? `<div class="search-result-snippet">${r.snippet}</div>` : ''}
            </div>
        `).join('');

        attachResultListeners(results);
    } catch (e) {
        results.innerHTML = `
            <div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);font-size:var(--text-sm)">
                Search error: ${escapeHtml(e.message)}
            </div>
        `;
    }
}

async function performTagSearch(query, results) {
    const rawTag = query.slice(1).trim();
    const tag = rawTag.split(/\s+/)[0]?.toLowerCase();
    if (!tag) {
        results.innerHTML = `
            <div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);font-size:var(--text-sm)">
                Type a tag after #
            </div>
        `;
        return;
    }

    try {
        const notes = await api.getNotesByTag(tag);
        if (!notes.length) {
            results.innerHTML = `
                <div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);font-size:var(--text-sm)">
                    No notes found for #${escapeHtml(tag)}
                </div>
            `;
            return;
        }

        results.innerHTML = notes.map((note, i) => `
            <div class="search-result-item${i === 0 ? ' selected' : ''}" data-path="${escapeHtml(note.path)}">
                <div class="search-result-title">${escapeHtml(note.title || note.path)}</div>
                <div class="search-result-path">${escapeHtml(note.path)}</div>
                <div class="search-result-snippet">Tag search: #${escapeHtml(tag)}</div>
            </div>
        `).join('');

        attachResultListeners(results);
    } catch (e) {
        results.innerHTML = `
            <div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);font-size:var(--text-sm)">
                Tag search error: ${escapeHtml(e.message)}
            </div>
        `;
    }
}

function attachResultListeners(results) {
    results.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('click', () => {
            if (onResultSelect && item.dataset.path) onResultSelect(item.dataset.path);
            closeSearch();
        });
        item.addEventListener('mouseenter', () => {
            results.querySelectorAll('.search-result-item').forEach(el => el.classList.remove('selected'));
            item.classList.add('selected');
        });
    });
}

function navigateResults(direction) {
    const results = document.getElementById('search-results');
    const items = Array.from(results.querySelectorAll('.search-result-item'));
    if (!items.length) return;

    const current = items.findIndex(el => el.classList.contains('selected'));
    items.forEach(el => el.classList.remove('selected'));

    let next = current + direction;
    if (next < 0) next = items.length - 1;
    if (next >= items.length) next = 0;

    items[next].classList.add('selected');
    items[next].scrollIntoView({ block: 'nearest' });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
