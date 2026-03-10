// ============================================
// Quick Capture - Popup for instant note capture
// ============================================

import { api } from './api.js';
import { showToast } from './sidebar.js';

let onNoteCreated = null;

export function initQuickCapture({ onCreated }) {
    onNoteCreated = onCreated;
}

export function openQuickCapture() {
    // Prevent duplicate
    if (document.getElementById('quick-capture-overlay')) return;

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'quick-capture-overlay';

    overlay.innerHTML = `
        <div class="modal dialog-modal" style="width:500px">
            <div class="dialog-header">
                <i data-lucide="zap" style="width:18px;height:18px;color:var(--accent)"></i>
                <span class="dialog-title">Quick Capture</span>
                <span style="margin-left:auto;font-size:var(--text-xs);color:var(--text-muted)">Saves to Inbox</span>
            </div>
            <div class="dialog-body" style="padding:var(--sp-4)">
                <textarea id="qc-content" class="qc-textarea" placeholder="Write your idea..." rows="4" autofocus></textarea>
                <div class="qc-tags-row">
                    <i data-lucide="hash" style="width:14px;height:14px;color:var(--text-muted)"></i>
                    <input type="text" id="qc-tags" class="dialog-input" placeholder="Tags (comma-separated)" style="border:none;background:none;padding:0;font-size:var(--text-xs)"/>
                </div>
            </div>
            <div class="dialog-footer">
                <span style="font-size:var(--text-xs);color:var(--text-muted)">Ctrl+Enter to save</span>
                <button class="btn btn-ghost" id="qc-cancel">Cancel</button>
                <button class="btn btn-primary" id="qc-save">Capture</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    if (typeof lucide !== 'undefined') lucide.createIcons();

    const textarea = overlay.querySelector('#qc-content');
    const tagsInput = overlay.querySelector('#qc-tags');
    const saveBtn = overlay.querySelector('#qc-save');
    const cancelBtn = overlay.querySelector('#qc-cancel');

    textarea.focus();

    const cleanup = () => {
        overlay.style.animation = 'fadeOut 100ms ease forwards';
        setTimeout(() => overlay.remove(), 100);
    };

    const save = async () => {
        const content = textarea.value.trim();
        if (!content) { cleanup(); return; }

        const tags = tagsInput.value.trim();
        const tagLine = tags ? `\n${tags.split(',').map(t => `#${t.trim()}`).join(' ')}` : '';
        const fullContent = content + tagLine;

        // Send to capture API → lands in inbox
        try {
            await api.capture(fullContent, 'quick-capture');
            showToast('Captured to inbox!', 'success');
            if (onNoteCreated) onNoteCreated(null);
        } catch (e) {
            showToast(`Error: ${e.message}`, 'error');
        }
        cleanup();
    };

    saveBtn.addEventListener('click', save);
    cancelBtn.addEventListener('click', cleanup);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) cleanup(); });

    textarea.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); save(); }
        if (e.key === 'Escape') { e.preventDefault(); cleanup(); }
    });
}
