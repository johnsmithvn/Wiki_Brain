// ============================================
// Table of Contents Generator
// ============================================

export function generateTOC(content) {
    const headings = [];
    const lines = content.split('\n');

    let inCodeBlock = false;
    for (const line of lines) {
        if (line.trim().startsWith('```')) {
            inCodeBlock = !inCodeBlock;
            continue;
        }
        if (inCodeBlock) continue;

        const match = line.match(/^(#{1,6})\s+(.+)/);
        if (match) {
            const level = match[1].length;
            const text = match[2].replace(/\*\*|__|`/g, '').trim();
            const id = text.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-');
            headings.push({ level, text, id });
        }
    }

    return headings;
}

export function renderTOC(headings) {
    const container = document.getElementById('toc-list');
    if (!headings.length) {
        container.innerHTML = '<li style="font-size:var(--text-xs);color:var(--text-muted)">No headings</li>';
        return;
    }

    container.innerHTML = headings.map(h =>
        `<li class="toc-item level-${h.level}" data-heading-id="${h.id}">${escapeHtml(h.text)}</li>`
    ).join('');

    container.querySelectorAll('.toc-item').forEach(item => {
        item.addEventListener('click', () => {
            // Scroll to heading in preview
            const preview = document.getElementById('preview-content') || document.getElementById('split-preview-content');
            if (preview) {
                const target = preview.querySelector(`#${item.dataset.headingId}`) ||
                    Array.from(preview.querySelectorAll('h1,h2,h3,h4,h5,h6')).find(
                        el => el.textContent.trim().toLowerCase().replace(/\s+/g, '-') === item.dataset.headingId
                    );
                if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
