// ============================================
// Editor Toolbar - Markdown formatting buttons
// ============================================

let activeTextarea = null;

export function initToolbar() {
    document.querySelectorAll('.toolbar-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const action = btn.dataset.action;
            if (activeTextarea && action) applyAction(action);
        });
    });
}

export function setActiveTextarea(textarea) {
    activeTextarea = textarea;
}

function applyAction(action) {
    const ta = activeTextarea;
    if (!ta) return;

    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = ta.value.substring(start, end);
    const before = ta.value.substring(0, start);
    const after = ta.value.substring(end);

    let insert = '';
    let cursorOffset = 0;

    switch (action) {
        case 'bold':
            insert = selected ? `**${selected}**` : '**bold**';
            cursorOffset = selected ? insert.length : 2;
            break;
        case 'italic':
            insert = selected ? `*${selected}*` : '*italic*';
            cursorOffset = selected ? insert.length : 1;
            break;
        case 'code':
            if (selected.includes('\n')) {
                insert = `\`\`\`\n${selected}\n\`\`\``;
            } else {
                insert = selected ? `\`${selected}\`` : '`code`';
            }
            cursorOffset = selected ? insert.length : 1;
            break;
        case 'link':
            insert = selected ? `[${selected}](url)` : '[text](url)';
            cursorOffset = insert.length - 1;
            break;
        case 'image':
            insert = selected ? `![${selected}](url)` : '![alt](url)';
            cursorOffset = insert.length - 1;
            break;
        case 'checkbox':
            insert = `- [ ] ${selected || 'task'}`;
            cursorOffset = insert.length;
            break;
        case 'heading':
            // Cycle heading levels or insert H2
            if (before.endsWith('### ')) {
                // Already H3, upgrade to H4
                ta.value = before.slice(0, -4) + '#### ' + (selected || 'heading') + after;
                ta.selectionStart = ta.selectionEnd = start + 1;
                ta.dispatchEvent(new Event('input'));
                return;
            }
            insert = `## ${selected || 'heading'}`;
            cursorOffset = insert.length;
            break;
        case 'quote':
            insert = selected
                ? selected.split('\n').map(l => `> ${l}`).join('\n')
                : '> quote';
            cursorOffset = insert.length;
            break;
        case 'hr':
            insert = '\n---\n';
            cursorOffset = insert.length;
            break;
        case 'ul':
            insert = selected
                ? selected.split('\n').map(l => `- ${l}`).join('\n')
                : '- item';
            cursorOffset = insert.length;
            break;
        case 'ol':
            insert = selected
                ? selected.split('\n').map((l, i) => `${i + 1}. ${l}`).join('\n')
                : '1. item';
            cursorOffset = insert.length;
            break;
        default:
            return;
    }

    ta.value = before + insert + after;
    ta.selectionStart = ta.selectionEnd = start + cursorOffset;
    ta.focus();
    ta.dispatchEvent(new Event('input'));
}
