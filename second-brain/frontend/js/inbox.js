// ============================================
// Inbox Panel - Browse, convert & manage captured entries
// ============================================

import { api } from './api.js';
import { showToast } from './sidebar.js';
import { showConfirm } from './modal.js';

let onConvertComplete = null;
let inboxData = [];       // [{ date, count }]
let expandedDates = {};   // { '2026-03-08': [entries] }
let selectedEntryId = null;

export function initInbox({ onConverted }) {
    onConvertComplete = onConverted;
}

// ---- Load inbox dates list ----
export async function loadInbox() {
    const container = document.getElementById('inbox-list');
    if (!container) return;

    try {
        inboxData = await api.getInboxDates();
        renderInboxDates(container);
    } catch (e) {
        console.error('Failed to load inbox:', e);
        container.innerHTML = `<div class="inbox-empty">Failed to load inbox</div>`;
    }
}

function renderInboxDates(container) {
    if (!inboxData.length) {
        container.innerHTML = `
            <div class="inbox-empty">
                <i data-lucide="inbox" style="width:32px;height:32px;color:var(--text-muted);opacity:0.4"></i>
                <span>No captures yet</span>
                <span class="inbox-empty-hint">Use Quick Capture (Ctrl+Shift+N) or the bookmarklet</span>
            </div>`;
        if (typeof lucide !== 'undefined') lucide.createIcons();
        return;
    }

    const totalEntries = inboxData.reduce((s, d) => s + d.count, 0);
    let html = `<div class="inbox-summary">${totalEntries} entry${totalEntries !== 1 ? 's' : ''}</div>`;

    for (const item of inboxData) {
        const isExpanded = expandedDates[item.date];
        const label = formatDateLabel(item.date);
        html += `
            <div class="inbox-date-group">
                <div class="inbox-date-header" data-date="${item.date}">
                    <span class="inbox-date-toggle ${isExpanded ? 'open' : ''}">
                        <i data-lucide="chevron-right" style="width:12px;height:12px"></i>
                    </span>
                    <span class="inbox-date-label">${label}</span>
                    <span class="inbox-date-badge">${item.count}</span>
                </div>
                <div class="inbox-entries ${isExpanded ? '' : 'collapsed'}" id="inbox-entries-${item.date}">
                    ${isExpanded ? renderEntries(expandedDates[item.date]) : '<div class="inbox-loading">Loading...</div>'}
                </div>
            </div>`;
    }

    container.innerHTML = html;
    if (typeof lucide !== 'undefined') lucide.createIcons();

    // Bind date header click → expand/collapse
    container.querySelectorAll('.inbox-date-header').forEach(header => {
        header.addEventListener('click', () => toggleDate(header.dataset.date));
    });

    // Bind entry action buttons for already-expanded dates
    bindEntryActions(container);
}

async function toggleDate(date) {
    const entriesEl = document.getElementById(`inbox-entries-${date}`);
    const header = document.querySelector(`.inbox-date-header[data-date="${date}"]`);
    if (!entriesEl || !header) return;

    const toggle = header.querySelector('.inbox-date-toggle');

    if (expandedDates[date]) {
        // Collapse
        delete expandedDates[date];
        entriesEl.classList.add('collapsed');
        toggle?.classList.remove('open');
    } else {
        // Expand + load entries
        toggle?.classList.add('open');
        entriesEl.classList.remove('collapsed');
        entriesEl.innerHTML = '<div class="inbox-loading">Loading...</div>';

        try {
            const entries = await api.getInboxEntries(date);
            expandedDates[date] = entries;
            entriesEl.innerHTML = renderEntries(entries);
            if (typeof lucide !== 'undefined') lucide.createIcons();
            bindEntryActions(entriesEl);
        } catch (e) {
            entriesEl.innerHTML = `<div class="inbox-empty">Failed to load entries</div>`;
            console.error('Failed to load inbox entries:', e);
        }
    }
}

function renderEntries(entries) {
    if (!entries || !entries.length) {
        return '<div class="inbox-empty">No entries</div>';
    }

    return entries.map(entry => {
        const typeIcon = entry.type === 'link' ? 'link' : entry.type === 'quote' ? 'quote' : 'file-text';
        const isSelected = entry.id === selectedEntryId;
        const contentPreview = truncate(entry.content, 120);
        const urlLine = entry.url ? `<div class="inbox-entry-url" title="${escapeHtml(entry.url)}">${escapeHtml(truncate(entry.url, 50))}</div>` : '';
        const tagsLine = entry.tags?.length
            ? `<div class="inbox-entry-tags">${entry.tags.map(t => `<span class="inbox-tag">#${escapeHtml(t)}</span>`).join(' ')}</div>`
            : '';

        return `
            <div class="inbox-entry ${isSelected ? 'selected' : ''}" data-id="${entry.id}" data-date="${entry.id.substring(0, 8).replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3')}">
                <div class="inbox-entry-header">
                    <i data-lucide="${typeIcon}" style="width:14px;height:14px;color:var(--accent);opacity:0.7;flex-shrink:0"></i>
                    <span class="inbox-entry-time">${entry.time}</span>
                    <span class="inbox-entry-source">${entry.source}</span>
                </div>
                <div class="inbox-entry-content">${escapeHtml(contentPreview)}</div>
                ${urlLine}
                ${tagsLine}
                <div class="inbox-entry-actions">
                    <button class="inbox-action-btn convert" data-action="convert" data-id="${entry.id}" title="Convert to note (Enter)">
                        <i data-lucide="file-output" style="width:13px;height:13px"></i>
                        <span>Convert</span>
                    </button>
                    <button class="inbox-action-btn archive" data-action="archive" data-id="${entry.id}" title="Archive (A)">
                        <i data-lucide="archive" style="width:13px;height:13px"></i>
                    </button>
                    <button class="inbox-action-btn delete" data-action="delete" data-id="${entry.id}" title="Delete (D)">
                        <i data-lucide="trash-2" style="width:13px;height:13px"></i>
                    </button>
                </div>
            </div>`;
    }).join('');
}

function bindEntryActions(container) {
    container.querySelectorAll('.inbox-action-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const action = btn.dataset.action;
            const entryId = btn.dataset.id;
            const entryEl = btn.closest('.inbox-entry');
            const date = findEntryDate(entryId);
            if (!date) return;

            if (action === 'convert') openConvertDialog(date, entryId, entryEl);
            else if (action === 'archive') handleArchive(date, entryId, entryEl);
            else if (action === 'delete') handleDelete(date, entryId, entryEl);
        });
    });

    // Click entry to select
    container.querySelectorAll('.inbox-entry').forEach(el => {
        el.addEventListener('click', () => {
            selectedEntryId = el.dataset.id;
            document.querySelectorAll('.inbox-entry.selected').forEach(s => s.classList.remove('selected'));
            el.classList.add('selected');
        });
    });
}

// ---- Convert Dialog ----
function openConvertDialog(date, entryId, entryEl) {
    const entry = findEntry(date, entryId);
    if (!entry) return;

    // Derive default title from content
    const firstLine = entry.content.split('\n')[0].trim();
    const defaultTitle = firstLine.length > 60 ? firstLine.substring(0, 60) + '...' : firstLine;

    // Remove existing dialog if any
    document.getElementById('inbox-convert-overlay')?.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'inbox-convert-overlay';
    overlay.innerHTML = `
        <div class="modal dialog-modal" style="width:480px">
            <div class="dialog-header">
                <i data-lucide="file-output" style="width:18px;height:18px;color:var(--accent)"></i>
                <span class="dialog-title">Convert to Note</span>
            </div>
            <div class="dialog-body" style="padding:var(--sp-4);display:flex;flex-direction:column;gap:var(--sp-3)">
                <div>
                    <label style="font-size:var(--text-xs);color:var(--text-secondary);margin-bottom:var(--sp-1);display:block">Title</label>
                    <input type="text" id="convert-title" class="dialog-input" value="${escapeAttr(defaultTitle)}" placeholder="Note title" autofocus>
                </div>
                <div>
                    <label style="font-size:var(--text-xs);color:var(--text-secondary);margin-bottom:var(--sp-1);display:block">Folder (optional)</label>
                    <input type="text" id="convert-folder" class="dialog-input" placeholder="e.g. ai, backend, daily">
                </div>
                <div>
                    <label style="font-size:var(--text-xs);color:var(--text-secondary);margin-bottom:var(--sp-1);display:block">Tags (comma-separated)</label>
                    <input type="text" id="convert-tags" class="dialog-input" value="${entry.tags?.join(', ') || ''}" placeholder="tag1, tag2">
                </div>
                <div class="inbox-convert-preview">
                    <label style="font-size:var(--text-xs);color:var(--text-secondary);margin-bottom:var(--sp-1);display:block">Content Preview</label>
                    <div class="inbox-convert-content">${escapeHtml(truncate(entry.content, 300))}</div>
                </div>
            </div>
            <div class="dialog-footer">
                <button class="btn btn-ghost" id="convert-cancel">Cancel</button>
                <button class="btn btn-primary" id="convert-confirm">
                    <i data-lucide="check" style="width:14px;height:14px"></i>
                    Convert
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    if (typeof lucide !== 'undefined') lucide.createIcons();

    const titleInput = overlay.querySelector('#convert-title');
    const folderInput = overlay.querySelector('#convert-folder');
    const tagsInput = overlay.querySelector('#convert-tags');
    titleInput.focus();
    titleInput.select();

    const cleanup = () => {
        overlay.style.animation = 'fadeOut 100ms ease forwards';
        setTimeout(() => overlay.remove(), 100);
    };

    const doConvert = async () => {
        const title = titleInput.value.trim();
        if (!title) {
            showToast('Title is required', 'error');
            return;
        }
        const folder = folderInput.value.trim();
        const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean);

        try {
            const result = await api.convertEntry(date, entryId, title, folder, tags);
            showToast(`Converted → ${result.path}`, 'success');
            cleanup();

            // Remove from local state
            if (expandedDates[date]) {
                expandedDates[date] = expandedDates[date].filter(e => e.id !== entryId);
            }
            // Refresh inbox
            await loadInbox();

            if (onConvertComplete) onConvertComplete(result.path);
        } catch (e) {
            showToast(`Convert failed: ${e.message}`, 'error');
        }
    };

    overlay.querySelector('#convert-confirm').addEventListener('click', doConvert);
    overlay.querySelector('#convert-cancel').addEventListener('click', cleanup);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) cleanup(); });
    titleInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); doConvert(); }
        if (e.key === 'Escape') cleanup();
    });
}

// ---- Archive & Delete ----
async function handleArchive(date, entryId, entryEl) {
    try {
        await api.archiveEntry(date, entryId);
        entryEl?.classList.add('inbox-entry-removing');
        setTimeout(async () => {
            if (expandedDates[date]) {
                expandedDates[date] = expandedDates[date].filter(e => e.id !== entryId);
            }
            await loadInbox();
        }, 200);
        showToast('Archived', 'info');
    } catch (e) {
        showToast(`Archive failed: ${e.message}`, 'error');
    }
}

async function handleDelete(date, entryId, entryEl) {
    const confirmed = await showConfirm(
        'This entry will be permanently deleted.',
        { title: 'Delete entry?', confirmText: 'Delete', danger: true }
    );
    if (!confirmed) return;

    try {
        await api.deleteEntry(date, entryId);
        entryEl?.classList.add('inbox-entry-removing');
        setTimeout(async () => {
            if (expandedDates[date]) {
                expandedDates[date] = expandedDates[date].filter(e => e.id !== entryId);
            }
            await loadInbox();
        }, 200);
        showToast('Deleted', 'info');
    } catch (e) {
        showToast(`Delete failed: ${e.message}`, 'error');
    }
}

// ---- Keyboard shortcuts for inbox panel ----
export function handleInboxKeyboard(e) {
    if (!selectedEntryId) return false;

    const date = findEntryDate(selectedEntryId);
    if (!date) return false;

    const entryEl = document.querySelector(`.inbox-entry[data-id="${selectedEntryId}"]`);

    if (e.key === 'Enter') {
        openConvertDialog(date, selectedEntryId, entryEl);
        return true;
    }
    if (e.key.toLowerCase() === 'a') {
        handleArchive(date, selectedEntryId, entryEl);
        return true;
    }
    if (e.key.toLowerCase() === 'd' && !e.ctrlKey && !e.altKey) {
        handleDelete(date, selectedEntryId, entryEl);
        return true;
    }

    // Arrow navigation
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        const allEntries = [...document.querySelectorAll('.inbox-entry')];
        const idx = allEntries.findIndex(el => el.dataset.id === selectedEntryId);
        const nextIdx = e.key === 'ArrowDown' ? idx + 1 : idx - 1;
        if (nextIdx >= 0 && nextIdx < allEntries.length) {
            selectedEntryId = allEntries[nextIdx].dataset.id;
            allEntries.forEach(el => el.classList.remove('selected'));
            allEntries[nextIdx].classList.add('selected');
            allEntries[nextIdx].scrollIntoView({ block: 'nearest' });
        }
        return true;
    }

    return false;
}

// ---- Helpers ----
function findEntryDate(entryId) {
    // Entry ID format: YYYYMMDD-HHmmss → date is YYYY-MM-DD
    const raw = entryId.substring(0, 8);
    return `${raw.substring(0, 4)}-${raw.substring(4, 6)}-${raw.substring(6, 8)}`;
}

function findEntry(date, entryId) {
    return expandedDates[date]?.find(e => e.id === entryId) || null;
}

function formatDateLabel(dateStr) {
    const today = new Date();
    const d = new Date(dateStr + 'T00:00:00');
    const diff = Math.floor((today - d) / 86400000);
    if (diff === 0) return `Today — ${formatMonth(d)}`;
    if (diff === 1) return `Yesterday — ${formatMonth(d)}`;
    return formatMonth(d);
}

function formatMonth(d) {
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function truncate(str, max) {
    if (!str) return '';
    return str.length > max ? str.substring(0, max) + '…' : str;
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeAttr(str) {
    return escapeHtml(str).replace(/'/g, '&#039;');
}
