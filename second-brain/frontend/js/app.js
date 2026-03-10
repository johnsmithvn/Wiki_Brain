// ============================================
// App Controller - Second Brain
// ============================================

import { api } from './api.js';
import { initSidebar, loadTree, loadTags, setActiveNote, showToast } from './sidebar.js';
import { initEditor, createEditor, getWordCount } from './editor.js';
import { initPreview, updateNotePaths, renderMarkdown } from './preview.js';
import { initSearch, openSearch, closeSearch } from './search.js';
import { initGraph, renderGraph, destroyGraph } from './graph.js';
import { generateTOC, renderTOC } from './toc.js';
import { showConfirm } from './modal.js';
import { initToolbar } from './toolbar.js';
import { initQuickCapture, openQuickCapture } from './quick-capture.js';
import { initInbox, loadInbox, handleInboxKeyboard } from './inbox.js';
import { initSlashMenu } from './slash-menu.js';
import { openTemplateModal } from './template-modal.js';
import { openShortcutsModal } from './shortcuts-modal.js';

const EXTERNAL_SYNC_MS = 4000;

// ---- State ----
const state = {
    currentNote: null,
    currentView: 'empty',
    currentSidebarTab: 'files',
    allNotePaths: [],
    saveTimeout: null,
    isDirty: false,
    externalSyncTimer: null,
    lastKnownModifiedAt: null,
    lastConflictModifiedAt: null,
};

// ---- Init ----
document.addEventListener('DOMContentLoaded', () => {
    if (typeof lucide !== 'undefined') lucide.createIcons();

    initSidebar({ onSelect: openNote, onNew: openTemplateCreateFlow });
    initEditor({ onChange: handleContentChange });
    initPreview({ onLinkClick: handleWikiLinkClick, notePaths: [] });
    initSearch({ onSelect: openNote });
    initGraph({ onClick: openNote });
    initToolbar();
    initQuickCapture({ onCreated: async (path) => { await loadTree(); await openNote(path); } });
    initInbox({
        onConverted: async (path) => {
            await loadTree();
            await loadTags();
            await loadAllNotePaths();
            await openNote(path);
        },
    });
    initSlashMenu();

    document.getElementById('btn-daily-note')?.addEventListener('click', openDailyNote);

    // Sidebar tabs
    initSidebarTabs();
    loadInbox(); // pre-load inbox badge count

    loadAllNotePaths();

    document.addEventListener('keydown', handleGlobalShortcuts);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    document.querySelectorAll('.view-tab').forEach(tab => {
        tab.addEventListener('click', () => switchView(tab.dataset.view));
    });

    document.getElementById('btn-shortcuts-help')?.addEventListener('click', openShortcutsModal);
    document.getElementById('btn-toggle-right-panel').addEventListener('click', toggleRightPanel);
});

// ---- Note Operations ----
async function openTemplateCreateFlow(parentPath = '') {
    await openTemplateModal({
        parentPath,
        onCreated: async (createdPath) => {
            await loadTree();
            await loadTags();
            await loadAllNotePaths();
            await openNote(createdPath);
        },
    });
}

async function openNote(path, options = {}) {
    const { promptCreate = true, preserveView = null, fromExternalReload = false } = options;

    if (!path) {
        state.currentNote = null;
        state.lastKnownModifiedAt = null;
        state.lastConflictModifiedAt = null;
        stopExternalSync();
        switchView('empty');
        setActiveNote(null);
        updateBreadcrumb(null);
        return;
    }

    let note;
    try {
        note = await api.getNote(path);
    } catch (e) {
        if (!promptCreate) {
            showToast(`Unable to open note: ${e.message}`, 'error');
            return;
        }

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
                await loadAllNotePaths();
                await openNote(newPath);
                showToast(`Created: ${name}`, 'success');
            } catch (err) {
                showToast(`Error: ${err.message}`, 'error');
            }
        }
        return;
    }

    try {
        state.currentNote = note;
        state.isDirty = false;
        state.lastKnownModifiedAt = note.modified_at || null;
        state.lastConflictModifiedAt = null;
        setActiveNote(path);
        updateBreadcrumb(note);
        updateBacklinks(note);

        document.getElementById('view-tabs').style.display = '';
        switchView(preserveView && preserveView !== 'empty' ? preserveView : 'editor');

        updateMetadata(note);
        trackRecentNote(path, note.title);
        updateStatusBar(note.content);
        startExternalSync();

        if (fromExternalReload) {
            showToast('Note reloaded from disk changes.', 'info');
        }
    } catch (uiErr) {
        console.error('UI error while opening note:', uiErr);
        showToast(`Error displaying note: ${uiErr.message}`, 'error');
    }
}

async function handleContentChange(content) {
    if (!state.currentNote) return;

    state.isDirty = true;
    state.currentNote.content = content;
    updateStatusBar(content);

    if (state.currentView === 'split') {
        const previewEl = document.getElementById('split-preview-content');
        renderMarkdown(content, previewEl);
    }

    const headings = generateTOC(content);
    renderTOC(headings);

    clearTimeout(state.saveTimeout);
    document.getElementById('status-save').textContent = 'Unsaved...';
    state.saveTimeout = setTimeout(() => saveCurrentNote(), 1500);
}

async function saveCurrentNote() {
    if (!state.currentNote || !state.isDirty) return;

    try {
        document.getElementById('status-save').textContent = 'Saving...';
        const updated = await api.updateNote(state.currentNote.path, state.currentNote.content);
        state.isDirty = false;
        state.lastKnownModifiedAt = updated?.modified_at || state.lastKnownModifiedAt;
        document.getElementById('status-save').textContent = 'Saved ✓';

        await loadAllNotePaths();
        await loadTags();

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

// ---- External Sync ----
function startExternalSync() {
    if (state.externalSyncTimer || !state.currentNote || document.hidden) return;
    state.externalSyncTimer = setInterval(checkExternalChange, EXTERNAL_SYNC_MS);
}

function stopExternalSync() {
    if (!state.externalSyncTimer) return;
    clearInterval(state.externalSyncTimer);
    state.externalSyncTimer = null;
}

function handleVisibilityChange() {
    if (document.hidden) {
        stopExternalSync();
        return;
    }
    startExternalSync();
    checkExternalChange();
}

async function checkExternalChange() {
    if (!state.currentNote || document.hidden) return;

    const currentPath = state.currentNote.path;
    try {
        const meta = await api.getNoteMeta(currentPath);
        if (!meta?.modified_at) return;

        const incomingTs = Date.parse(meta.modified_at);
        const knownTs = state.lastKnownModifiedAt ? Date.parse(state.lastKnownModifiedAt) : 0;
        if (!Number.isFinite(incomingTs) || incomingTs <= knownTs) return;

        if (state.isDirty) {
            if (state.lastConflictModifiedAt !== meta.modified_at) {
                state.lastConflictModifiedAt = meta.modified_at;
                showToast('File changed on disk while you have unsaved edits.', 'error');
            }
            return;
        }

        const previousView = state.currentView;
        await openNote(currentPath, {
            promptCreate: false,
            preserveView: previousView,
            fromExternalReload: true,
        });
    } catch (e) {
        // Ignore transient metadata failures; user-triggered flows keep full errors.
        console.debug('External sync check skipped:', e.message);
    }
}

// ---- View Switching ----
function switchView(view) {
    state.currentView = view;

    document.getElementById('empty-state').classList.add('hidden');
    document.getElementById('editor-view').classList.add('hidden');
    document.getElementById('preview-view').classList.add('hidden');
    document.getElementById('split-view').classList.add('hidden');
    document.getElementById('graph-view').classList.add('hidden');

    const toolbar = document.getElementById('editor-toolbar');
    if (toolbar) toolbar.style.display = (view === 'editor' || view === 'split') ? '' : 'none';

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

    if (view !== 'graph' && view !== 'empty') {
        const headings = generateTOC(content);
        renderTOC(headings);
    }
}

// ---- Sidebar Tabs ----
function initSidebarTabs() {
    document.querySelectorAll('.sidebar-tab').forEach(tab => {
        tab.addEventListener('click', () => switchSidebarTab(tab.dataset.tab));
    });
}

function switchSidebarTab(tabName) {
    state.currentSidebarTab = tabName;

    document.querySelectorAll('.sidebar-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tabName);
    });
    document.querySelectorAll('.sidebar-tab-content').forEach(c => {
        c.classList.toggle('active', c.dataset.tabContent === tabName);
    });

    if (tabName === 'inbox') {
        loadInbox();
    }

    if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ---- Wiki Link Navigation ----
function handleWikiLinkClick(target) {
    const targetLower = target.toLowerCase().replace(/\s+/g, '-');
    const resolved = state.allNotePaths.find(p => {
        const stem = p.split('/').pop().replace('.md', '').toLowerCase().replace(/\s+/g, '-');
        return stem === targetLower;
    });

    if (resolved) {
        openNote(resolved);
    } else {
        openNote(`${target}.md`);
    }
}

// ---- Helpers ----
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

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
    if (e.ctrlKey && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        openTemplateCreateFlow();
        return;
    }

    if (e.ctrlKey && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        openSearch();
        return;
    }

    if (e.ctrlKey && e.shiftKey && e.key === 'N') {
        e.preventDefault();
        openQuickCapture();
        return;
    }

    // Alt+I to switch to inbox tab
    if (e.altKey && e.key.toLowerCase() === 'i') {
        e.preventDefault();
        switchSidebarTab('inbox');
        return;
    }

    // Inbox keyboard shortcuts when inbox tab is active
    if (state.currentSidebarTab === 'inbox' && !e.ctrlKey && !e.altKey && !e.metaKey) {
        // Don't intercept when user is typing in an input/textarea/contenteditable
        const tag = document.activeElement?.tagName;
        const isEditable = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
            || document.activeElement?.isContentEditable;
        if (!isEditable && handleInboxKeyboard(e)) {
            e.preventDefault();
            return;
        }
    }

    if (e.altKey && e.key === '/') {
        e.preventDefault();
        openShortcutsModal();
        return;
    }

    // Keep Alt+N as alias for existing users.
    if (e.altKey && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        openTemplateCreateFlow();
        return;
    }

    if (e.altKey && e.key.toLowerCase() === 'd') {
        e.preventDefault();
        openDailyNote();
        return;
    }

    if (e.altKey && e.key.toLowerCase() === 'b') {
        e.preventDefault();
        document.getElementById('btn-collapse-sidebar').click();
        return;
    }

    if (e.altKey && e.key.toLowerCase() === 'e') {
        e.preventDefault();
        if (state.currentNote) {
            const next = state.currentView === 'editor' ? 'preview' : 'editor';
            switchView(next);
        }
        return;
    }

    if (e.altKey && e.key.toLowerCase() === 'g') {
        e.preventDefault();
        if (state.currentNote) switchView('graph');
        return;
    }

    if (e.key === 'Escape') {
        closeSearch();
        document.getElementById('context-menu').classList.add('hidden');
    }
}

async function openDailyNote() {
    try {
        const daily = await api.getDailyToday();
        await loadTree();
        await openNote(daily.path);
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

function updateMetadata(note) {
    const panel = document.getElementById('metadata-section');
    if (!panel) return;

    const { words, chars } = getWordCount();
    const created = note.created_at ? new Date(note.created_at).toLocaleDateString() : '—';
    const modified = note.modified_at ? new Date(note.modified_at).toLocaleDateString() : '—';

    panel.innerHTML = `
        <div class="right-panel-title">Note Info</div>
        <div class="metadata-row"><span class="metadata-key">Created</span><span class="metadata-value">${created}</span></div>
        <div class="metadata-row"><span class="metadata-key">Modified</span><span class="metadata-value">${modified}</span></div>
        <div class="metadata-row"><span class="metadata-key">Words</span><span class="metadata-value">${words}</span></div>
        <div class="metadata-row"><span class="metadata-key">Characters</span><span class="metadata-value">${chars}</span></div>
        <div class="metadata-row"><span class="metadata-key">Tags</span><span class="metadata-value">${(note.tags || []).length}</span></div>
        <div class="metadata-row"><span class="metadata-key">Links</span><span class="metadata-value">${(note.forward_links || []).length}</span></div>
        <div class="metadata-row"><span class="metadata-key">Backlinks</span><span class="metadata-value">${(note.backlinks || []).length}</span></div>
    `;
}

function trackRecentNote(path, title) {
    let recent = JSON.parse(localStorage.getItem('sb-recent') || '[]');
    recent = recent.filter(r => r.path !== path);
    recent.unshift({ path, title, time: Date.now() });
    recent = recent.slice(0, 10);
    localStorage.setItem('sb-recent', JSON.stringify(recent));
}
