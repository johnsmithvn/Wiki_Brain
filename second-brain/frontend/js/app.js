// ============================================
// App Controller - Second Brain
// ============================================

import { api } from './api.js';
import { initSidebar, loadTree, loadTags, setActiveNote, showToast } from './sidebar.js';
import { initEditor, createEditor, getContent, getWordCount, destroyEditor } from './editor.js';
import { initPreview, updateNotePaths, renderMarkdown } from './preview.js';
import { initSearch, openSearch, closeSearch } from './search.js';
import { initGraph, renderGraph, destroyGraph } from './graph.js';
import { generateTOC, renderTOC } from './toc.js';
import { showConfirm } from './modal.js';

// ---- State ----
const state = {
    currentNote: null,       // { path, title, content, ... }
    currentView: 'empty',    // 'empty' | 'editor' | 'preview' | 'split' | 'graph'
    allNotePaths: [],
    saveTimeout: null,
    isDirty: false,
};

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();

    initSidebar({ onSelect: openNote, onNew: () => {} });
    initEditor({ onChange: handleContentChange });
    initPreview({ onLinkClick: handleWikiLinkClick, notePaths: [] });
    initSearch({ onSelect: openNote });
    initGraph({ onClick: openNote });

    // Load all note paths for link resolution
    loadAllNotePaths();

    // Keyboard shortcuts
    document.addEventListener('keydown', handleGlobalShortcuts);

    // View tab clicks
    document.querySelectorAll('.view-tab').forEach(tab => {
        tab.addEventListener('click', () => switchView(tab.dataset.view));
    });

    // Right panel toggle
    document.getElementById('btn-toggle-right-panel').addEventListener('click', toggleRightPanel);
});

// ---- Note Operations ----
async function openNote(path) {
    if (!path) {
        state.currentNote = null;
        switchView('empty');
        setActiveNote(null);
        updateBreadcrumb(null);
        return;
    }

    try {
        const note = await api.getNote(path);
        state.currentNote = note;
        state.isDirty = false;
        setActiveNote(path);
        updateBreadcrumb(note);
        updateBacklinks(note);

        // Show tabs and switch to editor
        document.getElementById('view-tabs').style.display = '';
        switchView('editor');

        // Update status bar
        updateStatusBar(note.content);
    } catch (e) {
        // Note not found - maybe it's a wiki-link to new note
        const name = path.replace('.md', '');
        const shouldCreate = await showConfirm(
            `Note "${name}" doesn't exist yet. Would you like to create it?`,
            { title: 'Create Note', confirmText: 'Create', cancelText: 'Cancel' }
        );
        if (shouldCreate) {
            const newPath = path.endsWith('.md') ? path : `${path}.md`;
            try {
                await api.createNote(newPath, `# ${name}\n\n`);
                await loadTree();
                await loadTags();
                await openNote(newPath);
                showToast(`Created: ${name}`, 'success');
            } catch (err) {
                showToast(`Error: ${err.message}`, 'error');
            }
        }
    }
}

async function handleContentChange(content) {
    if (!state.currentNote) return;

    state.isDirty = true;
    state.currentNote.content = content;
    updateStatusBar(content);

    // Update preview if in split view
    if (state.currentView === 'split') {
        const previewEl = document.getElementById('split-preview-content');
        renderMarkdown(content, previewEl);
    }

    // Update TOC
    const headings = generateTOC(content);
    renderTOC(headings);

    // Auto-save with debounce
    clearTimeout(state.saveTimeout);
    document.getElementById('status-save').textContent = 'Unsaved...';
    state.saveTimeout = setTimeout(() => saveCurrentNote(), 1500);
}

async function saveCurrentNote() {
    if (!state.currentNote || !state.isDirty) return;

    try {
        document.getElementById('status-save').textContent = 'Saving...';
        await api.updateNote(state.currentNote.path, state.currentNote.content);
        state.isDirty = false;
        document.getElementById('status-save').textContent = 'Saved ✓';

        // Refresh links data
        await loadAllNotePaths();
        await loadTags();

        // Re-fetch backlinks
        try {
            const fresh = await api.getNote(state.currentNote.path);
            updateBacklinks(fresh);
        } catch (_) {}

        setTimeout(() => {
            if (!state.isDirty) {
                document.getElementById('status-save').textContent = 'Ready';
            }
        }, 2000);
    } catch (e) {
        document.getElementById('status-save').textContent = 'Save failed!';
        showToast(`Save error: ${e.message}`, 'error');
    }
}

// ---- View Switching ----
function switchView(view) {
    state.currentView = view;

    // Hide all views
    document.getElementById('empty-state').classList.add('hidden');
    document.getElementById('editor-view').classList.add('hidden');
    document.getElementById('preview-view').classList.add('hidden');
    document.getElementById('split-view').classList.add('hidden');
    document.getElementById('graph-view').classList.add('hidden');

    // Update tabs
    document.querySelectorAll('.view-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.view === view);
    });

    const content = state.currentNote?.content || '';

    switch (view) {
        case 'empty':
            document.getElementById('empty-state').classList.remove('hidden');
            document.getElementById('view-tabs').style.display = 'none';
            break;

        case 'editor':
            document.getElementById('editor-view').classList.remove('hidden');
            createEditor(document.getElementById('editor-pane'), content);
            break;

        case 'preview':
            document.getElementById('preview-view').classList.remove('hidden');
            renderMarkdown(content, document.getElementById('preview-content'));
            break;

        case 'split':
            document.getElementById('split-view').classList.remove('hidden');
            createEditor(document.getElementById('split-editor-pane'), content);
            renderMarkdown(content, document.getElementById('split-preview-content'));
            break;

        case 'graph':
            document.getElementById('graph-view').classList.remove('hidden');
            destroyGraph();
            setTimeout(() => {
                renderGraph(
                    document.getElementById('graph-view'),
                    state.currentNote?.path || null
                );
            }, 100);
            break;
    }

    // Update TOC
    if (view !== 'graph' && view !== 'empty') {
        const headings = generateTOC(content);
        renderTOC(headings);
    }
}

// ---- Wiki Link Navigation ----
function handleWikiLinkClick(target) {
    // Resolve target to a path
    const targetLower = target.toLowerCase().replace(/\s+/g, '-');
    const resolved = state.allNotePaths.find(p => {
        const stem = p.split('/').pop().replace('.md', '').toLowerCase().replace(/\s+/g, '-');
        return stem === targetLower;
    });

    if (resolved) {
        openNote(resolved);
    } else {
        // Create new note
        openNote(target + '.md');
    }
}

// ---- Helpers ----
async function loadAllNotePaths() {
    try {
        const notes = await api.listNotes();
        state.allNotePaths = notes.map(n => n.path);
        updateNotePaths(state.allNotePaths);
        document.getElementById('status-notes-count').textContent = `${notes.length} notes`;
    } catch (e) {
        console.error('Failed to load note paths:', e);
    }
}

function updateBreadcrumb(note) {
    const el = document.getElementById('breadcrumb');
    if (!note) {
        el.innerHTML = `<i data-lucide="brain" style="width:16px;height:16px;color:var(--accent)"></i><span>Second Brain</span>`;
    } else {
        const parts = note.path.replace('.md', '').split('/');
        el.innerHTML = parts.map((p, i) => {
            const isLast = i === parts.length - 1;
            return `${i > 0 ? '<span class="separator">/</span>' : ''}<span style="${isLast ? 'color:var(--text-primary);font-weight:500' : ''}">${escapeHtml(p)}</span>`;
        }).join('');
    }
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function updateBacklinks(note) {
    const container = document.getElementById('backlinks-list');
    if (!note.backlinks || !note.backlinks.length) {
        container.innerHTML = '<div style="font-size:var(--text-xs);color:var(--text-muted)">No backlinks</div>';
        return;
    }
    container.innerHTML = note.backlinks.map(link => {
        const name = link.split('/').pop().replace('.md', '');
        return `<div class="backlink-item" data-path="${escapeHtml(link)}">${escapeHtml(name)}</div>`;
    }).join('');

    container.querySelectorAll('.backlink-item').forEach(el => {
        el.addEventListener('click', () => openNote(el.dataset.path));
    });
}

function updateStatusBar(content) {
    const text = (content || '').trim();
    const words = text ? text.split(/\s+/).filter(w => w.length > 0).length : 0;
    document.getElementById('status-words').textContent = `${words} words`;
    document.getElementById('status-chars').textContent = `${text.length} chars`;
}

function toggleRightPanel() {
    document.getElementById('right-panel').classList.toggle('collapsed');
}

function handleGlobalShortcuts(e) {
    // Ctrl+K - Search (standard, override Chrome)
    if (e.ctrlKey && e.key === 'k') {
        e.preventDefault();
        openSearch();
        return;
    }
    // Alt+N - New note (avoid Ctrl+N = Chrome new window)
    if (e.altKey && e.key === 'n') {
        e.preventDefault();
        document.getElementById('btn-new-note').click();
        return;
    }
    // Alt+B - Toggle sidebar (avoid Ctrl+B = Chrome bookmarks)
    if (e.altKey && e.key === 'b') {
        e.preventDefault();
        document.getElementById('btn-collapse-sidebar').click();
        return;
    }
    // Alt+E - Toggle editor/preview
    if (e.altKey && e.key === 'e') {
        e.preventDefault();
        if (state.currentNote) {
            const next = state.currentView === 'editor' ? 'preview' : 'editor';
            switchView(next);
        }
        return;
    }
    // Alt+G - Graph view (avoid Ctrl+G = Chrome find next)
    if (e.altKey && e.key === 'g') {
        e.preventDefault();
        if (state.currentNote) switchView('graph');
        return;
    }
    // Escape - Close modals
    if (e.key === 'Escape') {
        closeSearch();
        document.getElementById('context-menu').classList.add('hidden');
    }
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
