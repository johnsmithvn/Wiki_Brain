const SHORTCUT_ROWS = [
    { key: 'Ctrl+N', action: 'Create note from template', note: 'Primary shortcut' },
    { key: 'Alt+N', action: 'Create note from template', note: 'Legacy alias' },
    { key: 'Ctrl+K', action: 'Open command palette', note: 'Search notes and commands' },
    { key: 'Ctrl+Shift+N', action: 'Quick Capture', note: 'Captures to inbox' },
    { key: 'Alt+I', action: 'Open Inbox tab', note: 'Switch sidebar to inbox' },
    { key: 'Ctrl+S', action: 'Save note', note: 'Works inside editor' },
    { key: 'Alt+/', action: 'Open shortcuts help', note: 'Same as keyboard icon button' },
    { key: 'Alt+D', action: 'Open daily note', note: 'Creates today note if missing' },
    { key: 'Alt+E', action: 'Toggle editor / preview', note: 'When note is open' },
    { key: 'Alt+G', action: 'Open graph view', note: 'When note is open' },
    { key: 'Alt+B', action: 'Toggle sidebar', note: 'Hide/show left panel' },
    { key: '/', action: 'Open slash menu', note: 'Inside editor' },
    { key: 'Enter', action: 'Convert inbox entry', note: 'When inbox entry is selected' },
    { key: 'A', action: 'Archive inbox entry', note: 'When inbox entry is selected' },
    { key: 'D', action: 'Delete inbox entry', note: 'When inbox entry is selected' },
    { key: '↑/↓', action: 'Navigate inbox entries', note: 'Arrow keys in inbox tab' },
    { key: 'Esc', action: 'Cancel / close', note: 'Closes popup/modal' },
];

function closeShortcutModal(overlay, handler) {
    document.removeEventListener('keydown', handler);
    overlay.style.animation = 'fadeOut 120ms ease forwards';
    const modal = overlay.querySelector('.shortcuts-modal');
    if (modal) modal.style.animation = 'slideUp 120ms ease forwards';
    setTimeout(() => overlay.remove(), 120);
}

export function openShortcutsModal() {
    const existing = document.getElementById('shortcuts-modal-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'shortcuts-modal-overlay';
    overlay.innerHTML = `
        <div class="modal shortcuts-modal">
            <div class="shortcuts-header">
                <div class="shortcuts-title">
                    <i data-lucide="keyboard"></i>
                    <span>Keyboard Shortcuts</span>
                </div>
                <button class="icon-btn" id="shortcuts-close" title="Close">
                    <i data-lucide="x"></i>
                </button>
            </div>
            <div class="shortcuts-body">
                <table class="shortcuts-table">
                    <thead>
                        <tr>
                            <th>Shortcut</th>
                            <th>Action</th>
                            <th>Note</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${SHORTCUT_ROWS.map(row => `
                            <tr>
                                <td><kbd>${row.key}</kbd></td>
                                <td>${row.action}</td>
                                <td>${row.note}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    if (typeof lucide !== 'undefined') lucide.createIcons();

    const onEsc = (e) => {
        if (e.key === 'Escape') {
            e.preventDefault();
            closeShortcutModal(overlay, onEsc);
        }
    };

    overlay.querySelector('#shortcuts-close')?.addEventListener('click', () => closeShortcutModal(overlay, onEsc));
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) {
            closeShortcutModal(overlay, onEsc);
        }
    });
    document.addEventListener('keydown', onEsc);
}
