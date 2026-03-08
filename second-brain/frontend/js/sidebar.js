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
let inlineRename = null;
let sortMode = 'time';  // 'time' (newest first) or 'alpha'
const UNTITLED_PREFIX = 'Untitled';
const MAX_UNTITLED_INDEX = 5000;

export function initSidebar({ onSelect, onNew }) {
    onNoteSelect = onSelect;
    onNewNote = onNew;

    document.getElementById('btn-collapse-sidebar').addEventListener('click', toggleSidebar);
    document.getElementById('btn-show-sidebar').addEventListener('click', toggleSidebar);
    document.getElementById('btn-new-note').addEventListener('click', () => requestNewNote());
    document.getElementById('btn-quick-add-file')?.addEventListener('click', () => handleQuickAddNote());
    document.getElementById('btn-quick-add-folder')?.addEventListener('click', () => handleQuickAddFolder());
    document.getElementById('file-tree')?.addEventListener('contextmenu', handleBlankTreeContextMenu);
    document.getElementById('btn-sort-toggle')?.addEventListener('click', toggleSort);

    // Root-level drop zone: drag a file out of a folder to root
    const fileTree = document.getElementById('file-tree');
    if (fileTree) {
        fileTree.addEventListener('dragover', (e) => {
            // Only show drop indicator on the container itself, not on children
            if (e.target === fileTree || e.target.closest('.tree-item') === null) {
                e.preventDefault();
                fileTree.classList.add('drag-over-root');
            }
        });
        fileTree.addEventListener('dragleave', (e) => {
            if (e.target === fileTree || !fileTree.contains(e.relatedTarget)) {
                fileTree.classList.remove('drag-over-root');
            }
        });
        fileTree.addEventListener('drop', (e) => {
            fileTree.classList.remove('drag-over-root');
            // Only handle drops on the container itself (root level)
            if (e.target === fileTree || e.target.closest('.tree-folder-item') === null) {
                e.preventDefault();
                handleDrop('');  // empty = root
            }
        });
    }

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

function sortTreeItems(items) {
    const sorted = [...items];
    sorted.sort((a, b) => {
        // Folders always first
        if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
        if (sortMode === 'time') {
            // Newest first (higher created_at = newer)
            return (b.created_at || 0) - (a.created_at || 0);
        }
        // Alphabetical
        return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' });
    });
    // Recursively sort children
    return sorted.map(item => {
        if (item.is_dir && item.children?.length) {
            return { ...item, children: sortTreeItems(item.children) };
        }
        return item;
    });
}

function toggleSort() {
    sortMode = sortMode === 'time' ? 'alpha' : 'time';
    const btn = document.getElementById('btn-sort-toggle');
    if (btn) {
        const icon = btn.querySelector('i');
        if (icon) {
            icon.setAttribute('data-lucide', sortMode === 'time' ? 'arrow-down-wide-narrow' : 'arrow-down-a-z');
        }
        btn.title = sortMode === 'time' ? 'Sort: Newest first' : 'Sort: Alphabetical';
    }
    renderTree(treeData);
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function renderTree(items) {
    const container = document.getElementById('file-tree');
    container.innerHTML = '';
    if (!items.length) {
        container.innerHTML = `<div style="padding:var(--sp-4);color:var(--text-muted);font-size:var(--text-sm)">No notes yet. Create one!</div>`;
        return;
    }
    const sorted = sortTreeItems(items);
    const frag = document.createDocumentFragment();
    buildTreeNodes(sorted, frag, 0);
    container.appendChild(frag);
    if (typeof lucide !== 'undefined') lucide.createIcons();
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
                <span class="tree-item-label">${escapeHtml(item.name)}</span>
            `;

            const children = document.createElement('div');
            children.className = 'tree-folder-children';
            buildTreeNodes(item.children || [], children, depth + 1);

            toggle.addEventListener('click', () => {
                const arrow = toggle.querySelector('.tree-folder-toggle');
                arrow.classList.toggle('open');
                children.classList.toggle('collapsed');
            });

            const folderLabel = toggle.querySelector('.tree-item-label');
            folderLabel?.addEventListener('dblclick', (e) => {
                e.preventDefault();
                e.stopPropagation();
                beginInlineRename(item.path, true);
            });

            // Context menu on folders
            toggle.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                showContextMenu(e, [
                    { label: 'Quick Add Note', icon: 'file-plus', action: () => handleQuickAddNote(item.path) },
                    { label: 'Quick Add Folder', icon: 'folder-plus', action: () => handleQuickAddFolder(item.path) },
                    { type: 'separator' },
                    { label: 'New Note Here', icon: 'file-plus', action: () => requestNewNote(item.path) },
                    { label: 'New Folder', icon: 'folder-plus', action: () => handleNewFolder(item.path) },
                    { label: 'Rename Folder', icon: 'pencil', action: () => beginInlineRename(item.path, true) },
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
                <span class="tree-item-label">${escapeHtml(item.name)}</span>
            `;
            noteEl.addEventListener('click', () => {
                if (onNoteSelect) onNoteSelect(item.path);
            });

            const noteLabel = noteEl.querySelector('.tree-item-label');
            noteLabel?.addEventListener('dblclick', (e) => {
                e.preventDefault();
                e.stopPropagation();
                beginInlineRename(item.path, false);
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
                    { label: 'Rename', icon: 'pencil', action: () => beginInlineRename(item.path, false) },
                    { type: 'separator' },
                    { label: 'Delete', icon: 'trash-2', danger: true, action: () => handleDelete(item.path) },
                ]);
            });

            parent.appendChild(noteEl);
        }
    }
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
    // Open the search modal with #tagName prefilled
    const modal = document.getElementById('search-modal');
    const input = document.getElementById('search-input');
    if (!modal || !input) {
        console.error('Search modal elements not found');
        return;
    }
    modal.classList.remove('hidden');
    input.value = `#${tagName}`;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.focus();
}

function normalizePath(path = '') {
    return String(path || '')
        .replace(/\\/g, '/')
        .replace(/^\/+|\/+$/g, '');
}

function joinPath(parentPath, childName) {
    const parent = normalizePath(parentPath);
    return parent ? `${parent}/${childName}` : childName;
}

function findTreeItemByPath(items, targetPath) {
    const normalizedTarget = normalizePath(targetPath).toLowerCase();
    for (const item of items) {
        const itemPath = normalizePath(item.path).toLowerCase();
        if (itemPath === normalizedTarget) return item;
        if (item.is_dir && item.children?.length) {
            const found = findTreeItemByPath(item.children, normalizedTarget);
            if (found) return found;
        }
    }
    return null;
}

function getFolderChildren(parentPath = '') {
    const normalizedParent = normalizePath(parentPath);
    if (!normalizedParent) return treeData;
    const folder = findTreeItemByPath(treeData, normalizedParent);
    if (!folder || !folder.is_dir) return [];
    return folder.children || [];
}

function hasPathInTree(targetPath) {
    const normalizedTarget = normalizePath(targetPath).toLowerCase();
    if (!normalizedTarget) return false;
    return Boolean(findTreeItemByPath(treeData, normalizedTarget));
}

function getNextUntitledName(parentPath = '', isDir = false) {
    const children = getFolderChildren(parentPath);
    const existingNames = new Set(
        children
            .filter(item => item.is_dir === isDir)
            .map(item => item.name.toLowerCase())
    );

    for (let i = 1; i <= MAX_UNTITLED_INDEX; i += 1) {
        const candidate = `${UNTITLED_PREFIX} ${i}`;
        if (!existingNames.has(candidate.toLowerCase())) {
            return candidate;
        }
    }
    throw new Error('Unable to allocate Untitled name');
}

function isConflictError(error) {
    return /already exists/i.test(error?.message || '');
}

function escapeSelector(value = '') {
    if (typeof CSS !== 'undefined' && CSS.escape) {
        return CSS.escape(value);
    }
    return String(value).replace(/["\\]/g, '\\$&');
}

function getRenameTarget(path, isDir) {
    const selector = isDir
        ? `.tree-folder-item[data-folder-path="${escapeSelector(path)}"] .tree-item-label`
        : `.tree-item[data-path="${escapeSelector(path)}"] .tree-item-label`;
    return document.querySelector(selector);
}

function getParentPath(path) {
    const normalized = normalizePath(path);
    const parts = normalized.split('/');
    parts.pop();
    return parts.join('/');
}

function handleBlankTreeContextMenu(e) {
    if (e.target.closest('.tree-item')) return;
    e.preventDefault();
    showContextMenu(e, [
        { label: 'Quick Add Note', icon: 'file-plus', action: () => handleQuickAddNote() },
        { label: 'Quick Add Folder', icon: 'folder-plus', action: () => handleQuickAddFolder() },
        { type: 'separator' },
        { label: 'New Note', icon: 'file-plus', action: () => requestNewNote() },
        { label: 'New Folder', icon: 'folder-plus', action: () => handleNewFolder('') },
    ]);
}

function cancelInlineRename() {
    if (!inlineRename) return;
    inlineRename.cancelled = true;
    inlineRename.input.remove();
    inlineRename.label.style.display = '';
    inlineRename = null;
}

function createInlineInput(label, initialValue) {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'tree-inline-rename';
    input.value = initialValue;
    label.style.display = 'none';
    label.parentElement.appendChild(input);
    input.addEventListener('click', (e) => e.stopPropagation());
    input.addEventListener('mousedown', (e) => e.stopPropagation());
    input.addEventListener('dblclick', (e) => e.stopPropagation());
    input.focus();
    input.select();
    return input;
}

async function commitInlineRename() {
    if (!inlineRename || inlineRename.pending) return;
    inlineRename.pending = true;

    const { path, isDir, label, input, originalName } = inlineRename;
    const nextName = input.value.trim();
    if (!nextName || nextName === originalName) {
        cancelInlineRename();
        return;
    }

    const parentPath = getParentPath(path);
    const newPath = isDir
        ? joinPath(parentPath, nextName)
        : joinPath(parentPath, `${nextName}.md`);

    try {
        if (isDir) {
            await api.renameFolder(path, newPath);
            await loadTree();
            const activePrefix = `${normalizePath(path)}/`;
            if (activeNotePath?.startsWith(activePrefix) && onNoteSelect) {
                const suffix = activeNotePath.slice(activePrefix.length);
                onNoteSelect(joinPath(newPath, suffix));
            }
            showToast(`Renamed folder to: ${nextName}`, 'success');
        } else {
            await api.renameNote(path, newPath);
            await loadTree();
            await loadTags();
            if (activeNotePath === path && onNoteSelect) {
                onNoteSelect(newPath);
            }
            showToast(`Renamed to: ${nextName}`, 'success');
        }
        label.textContent = nextName;
        input.remove();
        label.style.display = '';
        inlineRename = null;
    } catch (e) {
        showToast(`Rename failed: ${e.message}`, 'error');
        inlineRename.pending = false;
        input.focus();
        input.select();
    }
}

function beginInlineRename(path, isDir) {
    cancelInlineRename();

    const label = getRenameTarget(path, isDir);
    if (!label) {
        if (isDir) {
            handleRenameFolder(path);
        } else {
            handleRename(path);
        }
        return;
    }

    const originalName = isDir ? label.textContent.trim() : label.textContent.trim();
    const input = createInlineInput(label, originalName);
    inlineRename = {
        path,
        isDir,
        label,
        input,
        originalName,
        pending: false,
        cancelled: false,
    };

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            commitInlineRename();
            return;
        }
        if (e.key === 'Escape') {
            e.preventDefault();
            cancelInlineRename();
        }
    });

    input.addEventListener('blur', () => {
        if (!inlineRename || inlineRename.cancelled) return;
        commitInlineRename();
    });
}

async function handleDrop(targetFolderPath) {
    if (!dragSourcePath) return;
    const sourcePath = normalizePath(dragSourcePath);
    const fileName = sourcePath.split('/').pop();
    const newPath = joinPath(targetFolderPath, fileName);

    if (newPath.toLowerCase() === sourcePath.toLowerCase()) {
        dragSourcePath = null;
        return;
    }
    if (hasPathInTree(newPath)) {
        showToast(`Move failed: destination already exists (${fileName})`, 'error');
        dragSourcePath = null;
        return;
    }

    try {
        await api.renameNote(sourcePath, newPath);
        showToast(`Moved to ${targetFolderPath}`, 'success');
        await loadTree();
    } catch (e) {
        showToast(`Move failed: ${e.message}`, 'error');
    } finally {
        dragSourcePath = null;
    }
}

function requestNewNote(parentPath = '') {
    if (onNewNote) {
        onNewNote(parentPath);
        return;
    }
    handleNewNote(parentPath);
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
    const path = joinPath(parentPath, `${name}.md`);
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
    const path = joinPath(parentPath, name);
    try {
        await api.createFolder(path);
        await loadTree();
        showToast(`Created folder: ${name}`, 'success');
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function handleQuickAddNote(parentPath = '', attempt = 0) {
    if (attempt > 8) {
        showToast('Quick add note failed: too many name collisions', 'error');
        return;
    }
    try {
        await loadTree();
        const name = getNextUntitledName(parentPath, false);
        const path = joinPath(parentPath, `${name}.md`);
        await api.createNote(path, `# ${name}\n\n`);
        await loadTree();
        await loadTags();
        beginInlineRename(path, false);
        showToast('Quick note created. Enter to save, Esc to cancel rename.', 'info');
    } catch (e) {
        if (isConflictError(e)) {
            await handleQuickAddNote(parentPath, attempt + 1);
            return;
        }
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function handleQuickAddFolder(parentPath = '', attempt = 0) {
    if (attempt > 8) {
        showToast('Quick add folder failed: too many name collisions', 'error');
        return;
    }
    try {
        await loadTree();
        const name = getNextUntitledName(parentPath, true);
        const path = joinPath(parentPath, name);
        await api.createFolder(path);
        await loadTree();
        beginInlineRename(path, true);
        showToast('Quick folder created. Enter to save, Esc to cancel rename.', 'info');
    } catch (e) {
        if (isConflictError(e)) {
            await handleQuickAddFolder(parentPath, attempt + 1);
            return;
        }
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function handleRename(path, options = {}) {
    const currentName = path.split('/').pop().replace('.md', '');
    const newName = await showPrompt('Enter new name:', currentName, {
        title: options.title || 'Rename Note',
        placeholder: options.placeholder || currentName,
    });
    if (!newName || newName === currentName) return path;

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
        if (!options.skipSuccessToast) {
            showToast(`Renamed to: ${newName}`, 'success');
        }
        return newPath;
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
        return path;
    }
}

async function handleRenameFolder(path, options = {}) {
    const currentName = path.split('/').pop();
    const newName = await showPrompt('Enter new folder name:', currentName, {
        title: options.title || 'Rename Folder',
        placeholder: options.placeholder || currentName,
    });
    if (!newName || newName === currentName) return path;

    const parts = path.split('/');
    parts[parts.length - 1] = newName;
    const newPath = parts.join('/');

    try {
        await api.renameFolder(path, newPath);
        await loadTree();
        const activePrefix = `${normalizePath(path)}/`;
        if (activeNotePath?.startsWith(activePrefix) && onNoteSelect) {
            const suffix = activeNotePath.slice(activePrefix.length);
            onNoteSelect(joinPath(newPath, suffix));
        }
        if (!options.skipSuccessToast) {
            showToast(`Renamed folder to: ${newName}`, 'success');
        }
        return newPath;
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
        return path;
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
