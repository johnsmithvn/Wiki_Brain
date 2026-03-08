import { api } from './api.js';
import { showToast } from './sidebar.js';

const BLANK_ID = '__blank__';

function defaultNotePath(parentPath = '') {
    const base = parentPath ? `${parentPath.replace(/\\/g, '/').replace(/\/+$/g, '')}/` : '';
    return `${base}Untitled.md`;
}

function normalizeNotePath(rawPath) {
    let path = (rawPath || '').trim().replace(/\\/g, '/');
    if (!path) return '';
    path = path.replace(/^\/+/, '');
    if (!path.toLowerCase().endsWith('.md')) path += '.md';
    return path;
}

function noteTitleFromPath(path) {
    const clean = path.split('/').pop().replace(/\.md$/i, '');
    return clean || 'Untitled';
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str ?? '';
    return div.innerHTML;
}

function closeOverlay(overlay) {
    overlay.style.animation = 'fadeOut 120ms ease forwards';
    const modal = overlay.querySelector('.template-modal');
    if (modal) {
        modal.style.animation = 'slideUp 120ms ease forwards';
    }
    setTimeout(() => overlay.remove(), 120);
}

export async function openTemplateModal({ parentPath = '', onCreated } = {}) {
    const existing = document.getElementById('template-modal-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'template-modal-overlay';

    overlay.innerHTML = `
        <div class="modal template-modal">
            <div class="template-modal-header">
                <div class="template-modal-title-row">
                    <i data-lucide="file-plus" style="width:18px;height:18px;color:var(--accent)"></i>
                    <span>Create Note</span>
                </div>
                <button class="icon-btn" id="template-modal-close" title="Close">
                    <i data-lucide="x"></i>
                </button>
            </div>
            <div class="template-modal-body">
                <div class="template-list-pane">
                    <div class="template-pane-title">Template</div>
                    <div class="template-list" id="template-list"></div>
                </div>
                <div class="template-preview-pane">
                    <div class="template-pane-title">Preview</div>
                    <pre class="template-preview" id="template-preview">Loading templates...</pre>
                    <label class="template-path-label" for="template-note-path">Note path</label>
                    <input class="dialog-input" id="template-note-path" type="text" spellcheck="false" />
                    <div class="template-error" id="template-error"></div>
                </div>
            </div>
            <div class="dialog-footer">
                <button class="btn btn-ghost" id="template-cancel">Cancel</button>
                <button class="btn btn-primary" id="template-create">Create Note</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    if (typeof lucide !== 'undefined') lucide.createIcons();

    const closeBtn = overlay.querySelector('#template-modal-close');
    const cancelBtn = overlay.querySelector('#template-cancel');
    const createBtn = overlay.querySelector('#template-create');
    const listEl = overlay.querySelector('#template-list');
    const previewEl = overlay.querySelector('#template-preview');
    const pathInput = overlay.querySelector('#template-note-path');
    const errorEl = overlay.querySelector('#template-error');

    pathInput.value = defaultNotePath(parentPath);

    let selectedId = BLANK_ID;
    const previewCache = new Map();
    const items = [{ id: BLANK_ID, path: BLANK_ID, title: 'Blank note', name: 'Blank' }];
    let isClosed = false;

    function handleEscape(e) {
        if (e.key === 'Escape') {
            e.preventDefault();
            closeModal();
        }
    }

    function closeModal() {
        if (isClosed) return;
        isClosed = true;
        document.removeEventListener('keydown', handleEscape);
        closeOverlay(overlay);
    }

    function setError(message = '') {
        errorEl.textContent = message;
    }

    async function getTemplateContent(path) {
        if (path === BLANK_ID) return '';
        if (previewCache.has(path)) return previewCache.get(path);
        const data = await api.getTemplate(path);
        const content = data.content || '';
        previewCache.set(path, content);
        return content;
    }

    async function renderPreview() {
        if (selectedId === BLANK_ID) {
            previewEl.textContent = '# New Note\n\nStart writing...';
            return;
        }
        const current = items.find(item => item.id === selectedId);
        if (!current) {
            previewEl.textContent = 'Template not found';
            return;
        }
        previewEl.textContent = 'Loading template...';
        try {
            previewEl.textContent = await getTemplateContent(current.path);
        } catch (e) {
            previewEl.textContent = `Failed to load template: ${e.message}`;
        }
    }

    function renderTemplateList() {
        listEl.innerHTML = items.map(item => {
            const active = item.id === selectedId ? ' active' : '';
            const subtitle = item.path === BLANK_ID ? 'No template' : item.path;
            return `
                <button class="template-item${active}" data-template-id="${escapeHtml(item.id)}" type="button">
                    <span class="template-item-title">${escapeHtml(item.title || item.name)}</span>
                    <span class="template-item-path">${escapeHtml(subtitle)}</span>
                </button>
            `;
        }).join('');

        listEl.querySelectorAll('.template-item').forEach(btn => {
            btn.addEventListener('click', async () => {
                selectedId = btn.dataset.templateId;
                renderTemplateList();
                await renderPreview();
            });
        });
    }

    async function submitCreate() {
        setError('');
        const normalizedPath = normalizeNotePath(pathInput.value);
        if (!normalizedPath) {
            setError('Please enter a valid note path.');
            pathInput.focus();
            return;
        }

        let content = '';
        if (selectedId === BLANK_ID) {
            const title = noteTitleFromPath(normalizedPath);
            content = `# ${title}\n\n`;
        } else {
            const selected = items.find(item => item.id === selectedId);
            if (!selected) {
                setError('Please choose a template.');
                return;
            }
            try {
                content = await getTemplateContent(selected.path);
            } catch (e) {
                setError(`Failed to read template: ${e.message}`);
                return;
            }
        }

        createBtn.disabled = true;
        try {
            await api.createNote(normalizedPath, content);
            closeModal();
            showToast(`Created: ${noteTitleFromPath(normalizedPath)}`, 'success');
            if (onCreated) onCreated(normalizedPath);
        } catch (e) {
            setError(e.message);
            createBtn.disabled = false;
        }
    }

    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    createBtn.addEventListener('click', submitCreate);
    pathInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            submitCreate();
        }
    });
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) closeModal();
    });
    document.addEventListener('keydown', handleEscape);

    try {
        const response = await api.getTemplates();
        for (const template of response.templates || []) {
            items.push({
                id: template.path,
                path: template.path,
                title: template.title || template.name || template.path,
                name: template.name || template.path,
            });
        }
    } catch (e) {
        showToast(`Could not load templates: ${e.message}`, 'error');
    }

    renderTemplateList();
    await renderPreview();
    pathInput.focus();
    pathInput.select();
}
