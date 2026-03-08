// ============================================
// Slash Menu - In-editor command palette
// ============================================

const COMMANDS = [
    { key: 'todo', label: 'To-do List', icon: 'check-square', template: '- [ ] \n- [ ] \n- [ ] ' },
    { key: 'code', label: 'Code Block', icon: 'code', template: '```\n\n```' },
    { key: 'callout', label: 'Callout', icon: 'message-square', template: '> [!NOTE]\n> Your note here' },
    { key: 'table', label: 'Table', icon: 'table', template: '| Column 1 | Column 2 | Column 3 |\n|----------|----------|----------|\n| cell     | cell     | cell     |' },
    { key: 'heading', label: 'Heading', icon: 'heading', template: '## ' },
    { key: 'divider', label: 'Divider', icon: 'minus', template: '\n---\n' },
    { key: 'quote', label: 'Quote', icon: 'quote', template: '> ' },
    { key: 'image', label: 'Image', icon: 'image', template: '![alt](url)' },
    { key: 'link', label: 'Link', icon: 'link', template: '[[' },
];

let menuEl = null;
let activeTextarea = null;
let selectedIndex = 0;
let slashStartPos = -1;
let filterText = '';

export function initSlashMenu() {}

export function attachSlashMenu(textarea) {
    activeTextarea = textarea;
    textarea.addEventListener('input', handleInput);
    textarea.addEventListener('keydown', handleKeydown);
    textarea.addEventListener('blur', () => setTimeout(closeSlashMenu, 150));
}

export function detachSlashMenu() {
    if (activeTextarea) {
        activeTextarea.removeEventListener('input', handleInput);
        activeTextarea.removeEventListener('keydown', handleKeydown);
    }
    closeSlashMenu();
}

function handleInput() {
    const ta = activeTextarea;
    const pos = ta.selectionStart;
    const textBefore = ta.value.substring(0, pos);

    // Detect "/" at start of line
    const lineStart = textBefore.lastIndexOf('\n') + 1;
    const lineText = textBefore.substring(lineStart);

    if (lineText.startsWith('/')) {
        slashStartPos = lineStart;
        filterText = lineText.substring(1).toLowerCase();
        showSlashMenu(ta, filterText);
    } else {
        closeSlashMenu();
    }
}

function handleKeydown(e) {
    if (!menuEl) return;

    const filtered = getFilteredCommands();

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = (selectedIndex + 1) % filtered.length;
        updateSelection(filtered);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = (selectedIndex - 1 + filtered.length) % filtered.length;
        updateSelection(filtered);
    } else if (e.key === 'Enter' || e.key === 'Tab') {
        if (filtered.length > 0) {
            e.preventDefault();
            insertCommand(filtered[selectedIndex]);
        }
    } else if (e.key === 'Escape') {
        e.preventDefault();
        closeSlashMenu();
    }
}

function showSlashMenu(textarea, filter) {
    const filtered = getFilteredCommands();
    if (!filtered.length) { closeSlashMenu(); return; }

    selectedIndex = 0;

    if (!menuEl) {
        menuEl = document.createElement('div');
        menuEl.className = 'slash-menu';
        menuEl.id = 'slash-menu';
    }

    // Position near textarea caret
    const rect = textarea.getBoundingClientRect();
    menuEl.style.left = `${rect.left + 16}px`;
    menuEl.style.top = `${rect.top + 40}px`;

    renderMenu(filtered);

    if (!menuEl.parentNode) {
        document.body.appendChild(menuEl);
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
}

function renderMenu(filtered) {
    menuEl.innerHTML = filtered.map((cmd, i) =>
        `<div class="slash-menu-item${i === selectedIndex ? ' selected' : ''}" data-idx="${i}">
            <i data-lucide="${cmd.icon}" style="width:14px;height:14px"></i>
            <span class="slash-label">${cmd.label}</span>
            <span class="slash-hint">/${cmd.key}</span>
        </div>`
    ).join('');

    if (typeof lucide !== 'undefined') lucide.createIcons();

    menuEl.querySelectorAll('.slash-menu-item').forEach(el => {
        el.addEventListener('click', () => {
            const idx = parseInt(el.dataset.idx);
            insertCommand(filtered[idx]);
        });
    });
}

function updateSelection(filtered) {
    menuEl.querySelectorAll('.slash-menu-item').forEach((el, i) => {
        el.classList.toggle('selected', i === selectedIndex);
    });
}

function insertCommand(cmd) {
    const ta = activeTextarea;
    const pos = ta.selectionStart;
    const before = ta.value.substring(0, slashStartPos);
    const after = ta.value.substring(pos);

    ta.value = before + cmd.template + after;
    ta.selectionStart = ta.selectionEnd = slashStartPos + cmd.template.length;
    ta.focus();
    ta.dispatchEvent(new Event('input', { bubbles: true }));

    closeSlashMenu();
    // Prevent the slash menu from reopening
    slashStartPos = -1;
}

function getFilteredCommands() {
    if (!filterText) return COMMANDS;
    return COMMANDS.filter(c =>
        c.key.includes(filterText) || c.label.toLowerCase().includes(filterText)
    );
}

function closeSlashMenu() {
    if (menuEl && menuEl.parentNode) {
        menuEl.remove();
    }
    menuEl = null;
    slashStartPos = -1;
    filterText = '';
}
