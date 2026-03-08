// ============================================
// Markdown Editor - CodeMirror 6 Integration
// ============================================

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

    // Use a simple textarea-based editor as CodeMirror 6 CDN bundles vary
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
        padding: 32px 48px;
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

    let debounceTimer = null;
    textarea.addEventListener('input', () => {
        currentContent = textarea.value;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            if (onContentChange) onContentChange(textarea.value);
        }, 500);
    });

    wrapper.appendChild(textarea);
    container.appendChild(wrapper);

    // Store reference
    if (container.id === 'editor-pane') {
        editorView = textarea;
    } else {
        splitEditorView = textarea;
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
    editorView = null;
    splitEditorView = null;
    currentContent = '';
}
