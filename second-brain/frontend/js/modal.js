// ============================================
// Modal System - Custom Prompt/Confirm/Alert
// Replaces all native browser dialogs
// ============================================

/**
 * Show a custom prompt dialog (replaces window.prompt)
 * @param {string} message - Prompt message
 * @param {string} defaultValue - Initial input value
 * @param {object} opts - { placeholder, title }
 * @returns {Promise<string|null>} - User input or null if cancelled
 */
export function showPrompt(message, defaultValue = '', opts = {}) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.id = 'dialog-modal-overlay';

        const title = opts.title || message;
        const placeholder = opts.placeholder || '';

        overlay.innerHTML = `
            <div class="modal dialog-modal">
                <div class="dialog-header">
                    <i data-lucide="edit-3" style="width:18px;height:18px;color:var(--accent)"></i>
                    <span class="dialog-title">${escapeHtml(title)}</span>
                </div>
                <div class="dialog-body">
                    <input
                        type="text"
                        class="dialog-input"
                        id="dialog-input"
                        value="${escapeAttr(defaultValue)}"
                        placeholder="${escapeAttr(placeholder)}"
                        spellcheck="false"
                        autocomplete="off"
                    />
                </div>
                <div class="dialog-footer">
                    <button class="btn btn-ghost" id="dialog-cancel">Cancel</button>
                    <button class="btn btn-primary" id="dialog-ok">OK</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        if (typeof lucide !== 'undefined') lucide.createIcons();

        const input = overlay.querySelector('#dialog-input');
        const okBtn = overlay.querySelector('#dialog-ok');
        const cancelBtn = overlay.querySelector('#dialog-cancel');

        input.focus();
        input.select();

        const cleanup = (value) => {
            overlay.style.animation = 'fadeOut 100ms ease forwards';
            overlay.querySelector('.dialog-modal').style.animation = 'slideUp 100ms ease forwards';
            setTimeout(() => overlay.remove(), 100);
            resolve(value);
        };

        okBtn.addEventListener('click', () => {
            const val = input.value.trim();
            cleanup(val || null);
        });

        cancelBtn.addEventListener('click', () => cleanup(null));

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) cleanup(null);
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                okBtn.click();
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                cleanup(null);
            }
        });
    });
}

/**
 * Show a custom confirm dialog (replaces window.confirm)
 * @param {string} message - Confirmation message
 * @param {object} opts - { title, confirmText, cancelText, danger }
 * @returns {Promise<boolean>} - true if confirmed, false if cancelled
 */
export function showConfirm(message, opts = {}) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.id = 'dialog-modal-overlay';

        const title = opts.title || 'Confirm';
        const confirmText = opts.confirmText || 'Confirm';
        const cancelText = opts.cancelText || 'Cancel';
        const isDanger = opts.danger || false;
        const icon = isDanger ? 'alert-triangle' : 'help-circle';
        const iconColor = isDanger ? 'var(--danger)' : 'var(--accent)';
        const btnClass = isDanger ? 'btn btn-danger' : 'btn btn-primary';

        overlay.innerHTML = `
            <div class="modal dialog-modal">
                <div class="dialog-header">
                    <i data-lucide="${icon}" style="width:18px;height:18px;color:${iconColor}"></i>
                    <span class="dialog-title">${escapeHtml(title)}</span>
                </div>
                <div class="dialog-body">
                    <p class="dialog-message">${escapeHtml(message)}</p>
                </div>
                <div class="dialog-footer">
                    <button class="btn btn-ghost" id="dialog-cancel">${escapeHtml(cancelText)}</button>
                    <button class="${btnClass}" id="dialog-ok">${escapeHtml(confirmText)}</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        if (typeof lucide !== 'undefined') lucide.createIcons();

        const okBtn = overlay.querySelector('#dialog-ok');
        const cancelBtn = overlay.querySelector('#dialog-cancel');

        okBtn.focus();

        const cleanup = (value) => {
            overlay.style.animation = 'fadeOut 100ms ease forwards';
            overlay.querySelector('.dialog-modal').style.animation = 'slideUp 100ms ease forwards';
            setTimeout(() => overlay.remove(), 100);
            resolve(value);
        };

        okBtn.addEventListener('click', () => cleanup(true));
        cancelBtn.addEventListener('click', () => cleanup(false));

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) cleanup(false);
        });

        document.addEventListener('keydown', function handler(e) {
            if (e.key === 'Enter') { e.preventDefault(); cleanup(true); document.removeEventListener('keydown', handler); }
            if (e.key === 'Escape') { e.preventDefault(); cleanup(false); document.removeEventListener('keydown', handler); }
        });
    });
}

/**
 * Show a custom alert dialog (replaces window.alert)
 * @param {string} message - Alert message
 * @param {object} opts - { title, type: 'info'|'success'|'warning'|'error' }
 * @returns {Promise<void>}
 */
export function showAlert(message, opts = {}) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.id = 'dialog-modal-overlay';

        const title = opts.title || 'Notice';
        const type = opts.type || 'info';

        const iconMap = { info: 'info', success: 'check-circle', warning: 'alert-triangle', error: 'x-circle' };
        const colorMap = { info: 'var(--info)', success: 'var(--success)', warning: 'var(--warning)', error: 'var(--danger)' };
        const icon = iconMap[type] || 'info';
        const color = colorMap[type] || 'var(--info)';

        overlay.innerHTML = `
            <div class="modal dialog-modal">
                <div class="dialog-header">
                    <i data-lucide="${icon}" style="width:18px;height:18px;color:${color}"></i>
                    <span class="dialog-title">${escapeHtml(title)}</span>
                </div>
                <div class="dialog-body">
                    <p class="dialog-message">${escapeHtml(message)}</p>
                </div>
                <div class="dialog-footer">
                    <button class="btn btn-primary" id="dialog-ok">OK</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        if (typeof lucide !== 'undefined') lucide.createIcons();

        const okBtn = overlay.querySelector('#dialog-ok');
        okBtn.focus();

        const cleanup = () => {
            overlay.style.animation = 'fadeOut 100ms ease forwards';
            overlay.querySelector('.dialog-modal').style.animation = 'slideUp 100ms ease forwards';
            setTimeout(() => overlay.remove(), 100);
            resolve();
        };

        okBtn.addEventListener('click', cleanup);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) cleanup(); });
        document.addEventListener('keydown', function handler(e) {
            if (e.key === 'Enter' || e.key === 'Escape') { e.preventDefault(); cleanup(); document.removeEventListener('keydown', handler); }
        });
    });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escapeAttr(str) {
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
