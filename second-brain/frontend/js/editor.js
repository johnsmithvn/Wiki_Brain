// ============================================
// Markdown Editor - Textarea with toolbar + image paste + slash menu
// ============================================

import { api } from './api.js';
import { setActiveTextarea } from './toolbar.js';
import { attachSlashMenu, detachSlashMenu } from './slash-menu.js';
import { showToast } from './sidebar.js';

let editorView = null;
let splitEditorView = null;
let onContentChange = null;
let currentContent = '';

export function initEditor({ onChange }) {
    onContentChange = onChange;
}

export async function createEditor(container, content = '') {
    currentContent = content;
    container.innerHTML = '';

    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'height:100%;display:flex;flex-direction:column;';

    const textarea = document.createElement('textarea');
    textarea.className = 'editor-textarea';
    textarea.value = content;
    textarea.spellcheck = false;
    textarea.style.cssText = `
        flex: 1;
        width: 100%;
        background: var(--bg-base);
        color: var(--text-primary);
        border: none;
        outline: none;
        resize: none;
        padding: 24px 48px;
        font-family: var(--font-mono);
        font-size: var(--text-base);
        line-height: 1.75;
        tab-size: 4;
        max-width: 800px;
        margin: 0 auto;
        box-sizing: border-box;
    `;

    // Handle Tab key for indentation
    textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = textarea.selectionStart;
            const end = textarea.selectionEnd;
            textarea.value = textarea.value.substring(0, start) + '    ' + textarea.value.substring(end);
            textarea.selectionStart = textarea.selectionEnd = start + 4;
            textarea.dispatchEvent(new Event('input'));
        }
        // Ctrl+S
        if (e.ctrlKey && e.key === 's') {
            e.preventDefault();
            if (onContentChange) onContentChange(textarea.value);
        }
    });

    // Debounced input
    let debounceTimer = null;
    textarea.addEventListener('input', () => {
        currentContent = textarea.value;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            if (onContentChange) onContentChange(textarea.value);
        }, 500);
    });

    // Image paste handler
    textarea.addEventListener('paste', async (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;

        for (const item of items) {
            if (item.type.startsWith('image/')) {
                e.preventDefault();
                const file = item.getAsFile();
                if (!file) return;

                try {
                    const result = await api.uploadImage(file);
                    const markdownImg = `![image](${result.url})`;
                    const start = textarea.selectionStart;
                    textarea.value = textarea.value.substring(0, start) + markdownImg + textarea.value.substring(textarea.selectionEnd);
                    textarea.selectionStart = textarea.selectionEnd = start + markdownImg.length;
                    textarea.dispatchEvent(new Event('input'));
                    showToast('Image pasted!', 'success');
                } catch (err) {
                    showToast(`Image upload failed: ${err.message}`, 'error');
                }
                return;
            }
        }
    });

    wrapper.appendChild(textarea);
    container.appendChild(wrapper);

    // Register with toolbar and slash menu
    setActiveTextarea(textarea);
    attachSlashMenu(textarea);

    // Store reference
    if (container.id === 'editor-pane' || container.id === 'split-editor-pane') {
        if (container.id === 'editor-pane') {
            editorView = textarea;
        } else {
            splitEditorView = textarea;
        }
    }

    return textarea;
}

export function getContent() {
    if (editorView) return editorView.value;
    if (splitEditorView) return splitEditorView.value;
    return currentContent;
}

export function setContent(content) {
    currentContent = content;
    if (editorView) editorView.value = content;
    if (splitEditorView) splitEditorView.value = content;
}

export function getWordCount() {
    const text = currentContent.trim();
    if (!text) return { words: 0, chars: 0 };
    const words = text.split(/\s+/).filter(w => w.length > 0).length;
    return { words, chars: text.length };
}

export function destroyEditor() {
    detachSlashMenu();
    editorView = null;
    splitEditorView = null;
    currentContent = '';
}
