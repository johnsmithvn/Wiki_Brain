// ============================================
// Search - Command Palette Style
// ============================================

import { api } from './api.js';

let onResultSelect = null;
let debounceTimer = null;

export function initSearch({ onSelect }) {
    onResultSelect = onSelect;

    const modal = document.getElementById('search-modal');
    const input = document.getElementById('search-input');
    const results = document.getElementById('search-results');

    // Open search
    document.getElementById('btn-open-search').addEventListener('click', openSearch);

    // Input handler with debounce
    input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => performSearch(input.value), 250);
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
    document.getElementById('search-results').innerHTML = `
        <div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);font-size:var(--text-sm)">
            Type to search your knowledge base
        </div>
    `;
}

export function closeSearch() {
    document.getElementById('search-modal').classList.add('hidden');
}

async function performSearch(query) {
    const results = document.getElementById('search-results');
    if (!query.trim()) {
        results.innerHTML = `
            <div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);font-size:var(--text-sm)">
                Type to search your knowledge base
            </div>
        `;
        return;
    }

    try {
        const data = await api.search(query);
        if (!data.results.length) {
            results.innerHTML = `
                <div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);font-size:var(--text-sm)">
                    No results for "${escapeHtml(query)}"
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

        results.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', () => {
                if (onResultSelect) onResultSelect(item.dataset.path);
                closeSearch();
            });
            item.addEventListener('mouseenter', () => {
                results.querySelectorAll('.search-result-item').forEach(el => el.classList.remove('selected'));
                item.classList.add('selected');
            });
        });
    } catch (e) {
        results.innerHTML = `
            <div style="padding:var(--sp-4);text-align:center;color:var(--text-muted);font-size:var(--text-sm)">
                Search error: ${escapeHtml(e.message)}
            </div>
        `;
    }
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
