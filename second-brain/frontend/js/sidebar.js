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
let dragSourcePath = null;  // For drag & drop

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
            toggle.className = 'tree-item tree-folder-item';
            toggle.style.paddingLeft = `${16 + depth * 16}px`;
            toggle.dataset.folderPath = item.path;
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

            // Drop target
            toggle.addEventListener('dragover', (e) => { e.preventDefault(); toggle.classList.add('drag-over'); });
            toggle.addEventListener('dragleave', () => toggle.classList.remove('drag-over'));
            toggle.addEventListener('drop', (e) => { e.preventDefault(); toggle.classList.remove('drag-over'); handleDrop(item.path); });

            folderEl.appendChild(toggle);
            folderEl.appendChild(children);
            parent.appendChild(folderEl);
        } else {
            const noteEl = document.createElement('div');
            noteEl.className = 'tree-item';
            if (item.path === activeNotePath) noteEl.classList.add('active');
            noteEl.style.paddingLeft = `${16 + depth * 16}px`;
            noteEl.draggable = true;
            noteEl.dataset.path = item.path;
            noteEl.innerHTML = `
                <i data-lucide="file-text" style="width:14px;height:14px"></i>
                <span>${escapeHtml(item.name)}</span>
            `;
            noteEl.addEventListener('click', () => {
                if (onNoteSelect) onNoteSelect(item.path);
            });

            // Drag start
            noteEl.addEventListener('dragstart', (e) => {
                dragSourcePath = item.path;
                noteEl.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', item.path);
            });
            noteEl.addEventListener('dragend', () => noteEl.classList.remove('dragging'));

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

    const MAX_VISIBLE = 9;
    const visibleTags = tags.slice(0, MAX_VISIBLE);
    const hiddenCount = tags.length - MAX_VISIBLE;

    container.innerHTML = '';
    const chipRow = document.createElement('div');
    chipRow.className = 'tag-chips-row';
    chipRow.style.cssText = 'display:flex;flex-wrap:wrap;gap:var(--sp-1);';

    const buildChip = (t) => {
        const chip = document.createElement('span');
        chip.className = 'tag-chip';
        chip.dataset.tag = t.name;
        chip.innerHTML = `#${escapeHtml(t.name)} <span class="tag-count">${t.count}</span>`;
        chip.addEventListener('click', () => toggleTagExplorer(t.name, chip, container));
        return chip;
    };

    visibleTags.forEach(t => chipRow.appendChild(buildChip(t)));

    if (hiddenCount > 0) {
        const moreChip = document.createElement('span');
        moreChip.className = 'tag-chip tag-more';
        moreChip.textContent = `+${hiddenCount} more`;
        moreChip.addEventListener('click', () => {
            chipRow.innerHTML = '';
            tags.forEach(t => chipRow.appendChild(buildChip(t)));
            const collapseChip = document.createElement('span');
            collapseChip.className = 'tag-chip tag-more';
            collapseChip.textContent = '− collapse';
            collapseChip.addEventListener('click', () => renderTags(tags));
            chipRow.appendChild(collapseChip);
        });
        chipRow.appendChild(moreChip);
    }

    container.appendChild(chipRow);
}

async function toggleTagExplorer(tagName, chipEl, container) {
    // Remove existing tag-explorer panels
    container.querySelectorAll('.tag-explorer-panel').forEach(p => p.remove());

    // If this chip is already expanded, just close
    if (chipEl.classList.contains('tag-expanded')) {
        chipEl.classList.remove('tag-expanded');
        return;
    }
    // Close any other expanded
    container.querySelectorAll('.tag-expanded').forEach(c => c.classList.remove('tag-expanded'));
    chipEl.classList.add('tag-expanded');

    try {
        const notes = await api.getNotesByTag(tagName);
        const panel = document.createElement('div');
        panel.className = 'tag-explorer-panel';
        panel.style.cssText = 'width:100%;padding:var(--sp-1) 0;';

        (notes || []).forEach(note => {
            const item = document.createElement('div');
            item.className = 'tree-item';
            item.style.cssText = 'padding-left:var(--sp-4);font-size:var(--text-xs);';
            item.innerHTML = `<i data-lucide="file-text" style="width:12px;height:12px"></i> <span>${escapeHtml(note.title || note.path)}</span>`;
            item.addEventListener('click', () => { if (onNoteSelect) onNoteSelect(note.path); });
            panel.appendChild(item);
        });

        if (typeof lucide !== 'undefined') lucide.createIcons();

        // Insert panel right after the chip row
        container.appendChild(panel);
    } catch (e) {
        console.error('Failed to load tag notes:', e);
    }
}

async function handleDrop(targetFolderPath) {
    if (!dragSourcePath) return;
    const fileName = dragSourcePath.split('/').pop();
    const newPath = `${targetFolderPath}/${fileName}`;

    if (newPath === dragSourcePath) return; // Same location

    try {
        await api.renameNote(dragSourcePath, newPath);
        showToast(`Moved to ${targetFolderPath}`, 'success');
        await loadTree();
    } catch (e) {
        showToast(`Move failed: ${e.message}`, 'error');
    }
    dragSourcePath = null;
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
