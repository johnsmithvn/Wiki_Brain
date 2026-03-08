// ============================================
// Sidebar - File Tree + Tags
// ============================================

import { api } from './api.js';
import { showPrompt, showConfirm } from './modal.js';

let activeNotePath = null;
let treeData = [];
let tagData = [];
let onNoteSelect = null;
let onNewNote = null;

export function initSidebar({ onSelect, onNew }) {
    onNoteSelect = onSelect;
    onNewNote = onNew;

    document.getElementById('btn-collapse-sidebar').addEventListener('click', toggleSidebar);
    document.getElementById('btn-show-sidebar').addEventListener('click', toggleSidebar);
    document.getElementById('btn-new-note').addEventListener('click', () => handleNewNote());

    loadTree();
    loadTags();
}

export async function loadTree() {
    try {
        treeData = await api.getTree();
        renderTree(treeData);
    } catch (e) {
        console.error('Failed to load tree:', e);
    }
}

export async function loadTags() {
    try {
        const res = await api.getTags();
        tagData = res.tags || [];
        renderTags(tagData);
    } catch (e) {
        console.error('Failed to load tags:', e);
    }
}

function renderTree(items) {
    const container = document.getElementById('file-tree');
    container.innerHTML = '';
    if (!items.length) {
        container.innerHTML = `<div style="padding:var(--sp-4);color:var(--text-muted);font-size:var(--text-sm)">No notes yet. Create one!</div>`;
        return;
    }
    const frag = document.createDocumentFragment();
    buildTreeNodes(items, frag, 0);
    container.appendChild(frag);
}

function buildTreeNodes(items, parent, depth) {
    for (const item of items) {
        if (item.is_dir) {
            const folderEl = document.createElement('div');

            const toggle = document.createElement('div');
            toggle.className = 'tree-item';
            toggle.style.paddingLeft = `${16 + depth * 16}px`;
            toggle.innerHTML = `
                <span class="tree-folder-toggle open"><i data-lucide="chevron-right" style="width:12px;height:12px"></i></span>
                <i data-lucide="folder" style="width:14px;height:14px;color:var(--accent);opacity:0.7"></i>
                <span>${escapeHtml(item.name)}</span>
            `;

            const children = document.createElement('div');
            children.className = 'tree-folder-children';
            buildTreeNodes(item.children || [], children, depth + 1);

            toggle.addEventListener('click', () => {
                const arrow = toggle.querySelector('.tree-folder-toggle');
                arrow.classList.toggle('open');
                children.classList.toggle('collapsed');
            });

            // Context menu on folders
            toggle.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                showContextMenu(e, [
                    { label: 'New Note Here', icon: 'file-plus', action: () => handleNewNote(item.path) },
                    { label: 'New Folder', icon: 'folder-plus', action: () => handleNewFolder(item.path) },
                ]);
            });

            folderEl.appendChild(toggle);
            folderEl.appendChild(children);
            parent.appendChild(folderEl);
        } else {
            const noteEl = document.createElement('div');
            noteEl.className = 'tree-item';
            if (item.path === activeNotePath) noteEl.classList.add('active');
            noteEl.style.paddingLeft = `${16 + depth * 16}px`;
            noteEl.innerHTML = `
                <i data-lucide="file-text" style="width:14px;height:14px"></i>
                <span>${escapeHtml(item.name)}</span>
            `;
            noteEl.addEventListener('click', () => {
                if (onNoteSelect) onNoteSelect(item.path);
            });

            // Context menu on notes
            noteEl.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                showContextMenu(e, [
                    { label: 'Open', icon: 'file-text', action: () => onNoteSelect?.(item.path) },
                    { label: 'Rename', icon: 'pencil', action: () => handleRename(item.path) },
                    { type: 'separator' },
                    { label: 'Delete', icon: 'trash-2', danger: true, action: () => handleDelete(item.path) },
                ]);
            });

            parent.appendChild(noteEl);
        }
    }
    // Re-init Lucide icons in this subtree
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function renderTags(tags) {
    const container = document.getElementById('tag-list');
    if (!tags.length) {
        container.innerHTML = `<span style="font-size:var(--text-xs);color:var(--text-muted)">No tags</span>`;
        return;
    }

    const MAX_VISIBLE = 9; // ~3 rows of tags
    const visibleTags = tags.slice(0, MAX_VISIBLE);
    const hiddenCount = tags.length - MAX_VISIBLE;

    const buildChips = (tagList) => tagList.map(t =>
        `<span class="tag-chip" data-tag="${escapeHtml(t.name)}">#${escapeHtml(t.name)} <span class="tag-count">${t.count}</span></span>`
    ).join('');

    container.innerHTML = buildChips(visibleTags);

    if (hiddenCount > 0) {
        const moreChip = document.createElement('span');
        moreChip.className = 'tag-chip tag-more';
        moreChip.textContent = `+${hiddenCount} more`;
        moreChip.addEventListener('click', () => {
            // Expand: show all tags
            container.innerHTML = buildChips(tags);
            const collapseChip = document.createElement('span');
            collapseChip.className = 'tag-chip tag-more';
            collapseChip.textContent = '− collapse';
            collapseChip.addEventListener('click', () => renderTags(tags));
            container.appendChild(collapseChip);
            attachTagClickHandlers(container);
        });
        container.appendChild(moreChip);
    }

    attachTagClickHandlers(container);
}

function attachTagClickHandlers(container) {
    container.querySelectorAll('.tag-chip:not(.tag-more)').forEach(chip => {
        chip.addEventListener('click', () => {
            const searchInput = document.getElementById('search-input');
            document.getElementById('search-modal').classList.remove('hidden');
            searchInput.value = `#${chip.dataset.tag}`;
            searchInput.dispatchEvent(new Event('input'));
            searchInput.focus();
        });
    });
}

export function setActiveNote(path) {
    activeNotePath = path;
    document.querySelectorAll('.tree-item').forEach(el => el.classList.remove('active'));
    // Re-render to highlight
    renderTree(treeData);
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const btnShow = document.getElementById('btn-show-sidebar');
    sidebar.classList.toggle('collapsed');
    btnShow.style.display = sidebar.classList.contains('collapsed') ? '' : 'none';
}

async function handleNewNote(parentPath) {
    const name = await showPrompt('Enter note name:', '', { title: 'New Note', placeholder: 'My Note' });
    if (!name) return;
    const path = parentPath ? `${parentPath}/${name}.md` : `${name}.md`;
    try {
        await api.createNote(path, `# ${name}\n\n`);
        await loadTree();
        await loadTags();
        if (onNoteSelect) onNoteSelect(path);
        showToast(`Created: ${name}`, 'success');
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function handleNewFolder(parentPath) {
    const name = await showPrompt('Enter folder name:', '', { title: 'New Folder', placeholder: 'My Folder' });
    if (!name) return;
    const path = parentPath ? `${parentPath}/${name}` : name;
    try {
        await api.createFolder(path);
        await loadTree();
        showToast(`Created folder: ${name}`, 'success');
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function handleRename(path) {
    const currentName = path.split('/').pop().replace('.md', '');
    const newName = await showPrompt('Enter new name:', currentName, { title: 'Rename Note' });
    if (!newName || newName === currentName) return;
    const parts = path.split('/');
    parts[parts.length - 1] = newName + '.md';
    const newPath = parts.join('/');
    try {
        await api.renameNote(path, newPath);
        await loadTree();
        await loadTags();
        if (activeNotePath === path && onNoteSelect) {
            onNoteSelect(newPath);
        }
        showToast(`Renamed to: ${newName}`, 'success');
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function handleDelete(path) {
    const name = path.split('/').pop().replace('.md', '');
    const confirmed = await showConfirm(
        `Delete "${name}"? This action cannot be undone.`,
        { title: 'Delete Note', confirmText: 'Delete', danger: true }
    );
    if (!confirmed) return;
    try {
        await api.deleteNote(path);
        await loadTree();
        await loadTags();
        if (activeNotePath === path) {
            activeNotePath = null;
            if (onNoteSelect) onNoteSelect(null);
        }
        showToast(`Deleted: ${name}`, 'success');
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

// Context menu
function showContextMenu(event, items) {
    const menu = document.getElementById('context-menu');
    menu.innerHTML = items.map(item => {
        if (item.type === 'separator') return '<div class="context-menu-separator"></div>';
        return `<div class="context-menu-item${item.danger ? ' danger' : ''}" data-action="${item.label}">
            <i data-lucide="${item.icon}" style="width:14px;height:14px"></i>
            <span>${item.label}</span>
        </div>`;
    }).join('');

    menu.style.left = `${event.clientX}px`;
    menu.style.top = `${event.clientY}px`;
    menu.classList.remove('hidden');

    if (typeof lucide !== 'undefined') lucide.createIcons();

    const actionMap = {};
    items.forEach(item => { if (item.action) actionMap[item.label] = item.action; });

    menu.querySelectorAll('.context-menu-item').forEach(el => {
        el.addEventListener('click', () => {
            const action = actionMap[el.dataset.action];
            if (action) action();
            menu.classList.add('hidden');
        });
    });

    const close = (e) => {
        if (!menu.contains(e.target)) {
            menu.classList.add('hidden');
            document.removeEventListener('click', close);
        }
    };
    setTimeout(() => document.addEventListener('click', close), 10);
}

// Toast
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 200ms ease';
        setTimeout(() => toast.remove(), 200);
    }, 3000);
}

export { showToast };

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
