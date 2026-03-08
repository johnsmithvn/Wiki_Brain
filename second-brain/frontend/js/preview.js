// ============================================
// Markdown Preview Renderer
// ============================================

let onWikiLinkClick = null;
let allNotePaths = [];

export function initPreview({ onLinkClick, notePaths }) {
    onWikiLinkClick = onLinkClick;
    allNotePaths = notePaths || [];

    // Configure marked with custom renderer for heading IDs
    if (typeof marked !== 'undefined') {
        const renderer = new marked.Renderer();

        // Generate heading IDs matching TOC's id generation
        renderer.heading = function ({ text, depth }) {
            const raw = stripHtmlTags(text);
            const id = raw.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
            return `<h${depth} id="${id}">${text}</h${depth}>`;
        };

        marked.setOptions({
            breaks: true,
            gfm: true,
            renderer,
        });
    }
}

export function updateNotePaths(paths) {
    allNotePaths = paths;
}

export function renderMarkdown(content, container) {
    if (!content) {
        container.innerHTML = '<p style="color:var(--text-muted)">Empty note</p>';
        return;
    }

    // Pre-process: replace [[wiki-links]] with custom markup
    let processed = content.replace(
        /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
        (match, target, alias) => {
            const displayText = alias || target;
            const isResolved = isLinkResolved(target.trim());
            const cssClass = isResolved ? 'wiki-link' : 'wiki-link broken';
            return `<a class="${cssClass}" data-wiki-link="${encodeURIComponent(target.trim())}">${escapeHtml(displayText.trim())}</a>`;
        }
    );

    // Pre-process: replace inline #tags
    processed = processed.replace(
        /(?:^|\s)#([a-zA-Z\u00C0-\u024F][a-zA-Z0-9_\-/]*)/gm,
        (match, tag) => {
            return ` <span class="inline-tag" data-tag="${escapeHtml(tag)}">#${escapeHtml(tag)}</span>`;
        }
    );

    // Render with marked
    if (typeof marked !== 'undefined') {
        container.innerHTML = marked.parse(processed);
    } else {
        container.innerHTML = `<pre>${escapeHtml(content)}</pre>`;
    }

    // Attach wiki-link click handlers
    container.querySelectorAll('.wiki-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const target = decodeURIComponent(link.dataset.wikiLink);
            if (onWikiLinkClick) onWikiLinkClick(target);
        });
    });

    // Attach tag click handlers
    container.querySelectorAll('.inline-tag').forEach(tag => {
        tag.addEventListener('click', () => {
            const searchInput = document.getElementById('search-input');
            document.getElementById('search-modal').classList.remove('hidden');
            searchInput.value = `#${tag.dataset.tag}`;
            searchInput.dispatchEvent(new Event('input', { bubbles: true }));
            searchInput.focus();
        });
    });
}

function isLinkResolved(linkText) {
    const linkLower = linkText.toLowerCase().replace(/\s+/g, '-');
    return allNotePaths.some(path => {
        const stem = path.split('/').pop().replace('.md', '').toLowerCase().replace(/\s+/g, '-');
        return stem === linkLower;
    });
}

function stripHtmlTags(html) {
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || '';
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
