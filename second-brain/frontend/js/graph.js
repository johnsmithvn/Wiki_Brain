// ============================================
// Graph View - D3.js Force-Directed + Filters
// ============================================

import { api } from './api.js';

let simulation = null;
let svg = null;
let zoom = null;
let onNodeClick = null;

// Current filter state
const filterState = {
    tags: [],
    folders: [],
    depth: 0,
};

export function initGraph({ onClick }) {
    onNodeClick = onClick;
    initFilterPanel();
}

// ── Filter Panel Logic ──────────────────────────

function initFilterPanel() {
    const toggleBtn = document.getElementById('btn-graph-filter-toggle');
    const closeBtn = document.getElementById('btn-close-graph-filter');
    const panel = document.getElementById('graph-filter-panel');
    const applyBtn = document.getElementById('btn-graph-filter-apply');
    const resetBtn = document.getElementById('btn-graph-filter-reset');
    const depthSlider = document.getElementById('graph-filter-depth');
    const depthVal = document.getElementById('graph-filter-depth-val');

    if (!toggleBtn || !panel) return;

    toggleBtn.addEventListener('click', () => {
        panel.classList.toggle('collapsed');
        if (!panel.classList.contains('collapsed')) {
            loadFilterOptions();
        }
    });

    closeBtn?.addEventListener('click', () => {
        panel.classList.add('collapsed');
    });

    depthSlider?.addEventListener('input', () => {
        if (depthVal) depthVal.textContent = depthSlider.value;
    });

    applyBtn?.addEventListener('click', () => {
        applyFilters();
    });

    resetBtn?.addEventListener('click', () => {
        resetFilters();
    });
}

async function loadFilterOptions() {
    const tagContainer = document.getElementById('graph-filter-tags');
    const folderSelect = document.getElementById('graph-filter-folder');

    // Load tags
    try {
        const response = await api.getTags();
        const tagList = response.tags || [];
        if (tagContainer) {
            tagContainer.innerHTML = '';
            for (const tagItem of tagList) {
                const chip = document.createElement('span');
                chip.className = 'graph-filter-tag';
                chip.textContent = `#${tagItem.name}`;
                chip.dataset.tag = tagItem.name;
                if (filterState.tags.includes(tagItem.name)) {
                    chip.classList.add('active');
                }
                chip.addEventListener('click', () => {
                    chip.classList.toggle('active');
                });
                tagContainer.appendChild(chip);
            }
        }
    } catch { /* silent */ }

    // Load folders from file tree
    try {
        const tree = await api.getTree();
        if (folderSelect) {
            // Preserve current selection
            const current = folderSelect.value;
            folderSelect.innerHTML = '<option value="">All folders</option>';
            extractFolders(tree, folderSelect);
            folderSelect.value = current;
        }
    } catch { /* silent */ }
}

function extractFolders(tree, select, prefix = '') {
    for (const item of tree) {
        if (item.is_dir) {
            const path = prefix ? `${prefix}/${item.name}` : item.name;
            const opt = document.createElement('option');
            opt.value = path;
            opt.textContent = path;
            select.appendChild(opt);
            if (item.children?.length) {
                extractFolders(item.children, select, path);
            }
        }
    }
}

function applyFilters() {
    const tagContainer = document.getElementById('graph-filter-tags');
    const folderSelect = document.getElementById('graph-filter-folder');
    const depthSlider = document.getElementById('graph-filter-depth');

    // Collect selected tags
    filterState.tags = [];
    tagContainer?.querySelectorAll('.graph-filter-tag.active').forEach(chip => {
        filterState.tags.push(chip.dataset.tag);
    });

    // Collect selected folder
    filterState.folders = [];
    const selectedFolder = folderSelect?.value;
    if (selectedFolder) {
        filterState.folders.push(selectedFolder);
    }

    // Collect depth
    filterState.depth = parseInt(depthSlider?.value || '0', 10);

    // Re-render graph with filters
    const container = document.getElementById('graph-view');
    if (container) {
        renderGraph(container, null);
    }
}

function resetFilters() {
    filterState.tags = [];
    filterState.folders = [];
    filterState.depth = 0;

    // Reset UI
    document.getElementById('graph-filter-tags')?.querySelectorAll('.active').forEach(c => c.classList.remove('active'));
    const folderSelect = document.getElementById('graph-filter-folder');
    if (folderSelect) folderSelect.value = '';
    const depthSlider = document.getElementById('graph-filter-depth');
    if (depthSlider) depthSlider.value = '0';
    const depthVal = document.getElementById('graph-filter-depth-val');
    if (depthVal) depthVal.textContent = '0';

    // Re-render with no filters
    const container = document.getElementById('graph-view');
    if (container) {
        renderGraph(container, null);
    }
}

// ── Graph Rendering ─────────────────────────────

export async function renderGraph(container, focusPath = null) {
    container.innerHTML = '';

    // Re-insert the filter panel and controls (they were cleared)
    await restoreGraphUI(container);

    let data;
    try {
        if (focusPath) {
            data = await api.getLocalGraph(focusPath, 2);
        } else {
            const hasFilters = filterState.tags.length > 0 || filterState.folders.length > 0;
            data = await api.getGraph(hasFilters ? filterState : {});
        }
    } catch (e) {
        container.innerHTML += `<div class="empty-state"><p>Failed to load graph</p></div>`;
        return;
    }

    if (!data.nodes.length) {
        const msg = (filterState.tags.length || filterState.folders.length)
            ? 'No notes match the current filters'
            : 'No connections yet';
        const hint = (filterState.tags.length || filterState.folders.length)
            ? 'Try adjusting your filters or resetting'
            : 'Create notes with [[wiki-links]] to see the graph';
        container.innerHTML += `<div class="empty-state">
            <i data-lucide="git-branch" style="width:48px;height:48px;opacity:0.3"></i>
            <h3>${msg}</h3>
            <p>${hint}</p>
        </div>`;
        if (typeof lucide !== 'undefined') lucide.createIcons();
        return;
    }

    const width = container.clientWidth;
    const height = container.clientHeight;

    svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const g = svg.append('g');

    zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => g.attr('transform', event.transform));

    svg.call(zoom);
    svg.call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(0.8));

    // Links
    const link = g.append('g')
        .selectAll('line')
        .data(data.edges)
        .join('line')
        .attr('class', 'graph-link');

    // Nodes
    const node = g.append('g')
        .selectAll('g')
        .data(data.nodes)
        .join('g')
        .attr('class', d => `graph-node ${d.group}`)
        .call(d3.drag()
            .on('start', dragStarted)
            .on('drag', dragged)
            .on('end', dragEnded));

    node.append('circle')
        .attr('r', d => Math.max(5, Math.min(15, d.size * 3 + 4)))
        .attr('fill', d => {
            if (d.group === 'center') return 'var(--accent)';
            if (d.group === 'seed') return 'var(--accent)';
            if (d.group === 'expanded') return 'var(--text-muted)';
            return 'var(--bg-active)';
        })
        .on('click', (event, d) => {
            if (onNodeClick) onNodeClick(d.id);
        });

    node.append('text')
        .text(d => d.label)
        .attr('dy', d => Math.max(5, Math.min(15, d.size * 3 + 4)) + 14)
        .attr('text-anchor', 'middle')
        .style('font-size', '11px')
        .style('fill', 'var(--text-secondary)')
        .style('pointer-events', 'none');

    // Tooltip
    const tooltip = d3.select(container)
        .append('div')
        .attr('class', 'graph-tooltip')
        .style('display', 'none');

    node.on('mouseenter', (event, d) => {
        tooltip.text(d.label)
            .style('display', 'block')
            .style('left', `${event.offsetX + 10}px`)
            .style('top', `${event.offsetY - 10}px`);
    }).on('mouseleave', () => {
        tooltip.style('display', 'none');
    });

    // Simulation
    simulation = d3.forceSimulation(data.nodes)
        .force('link', d3.forceLink(data.edges).id(d => d.id).distance(80))
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(0, 0))
        .force('collision', d3.forceCollide().radius(30))
        .on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);

            node.attr('transform', d => `translate(${d.x},${d.y})`);
        });

    // Graph controls
    document.getElementById('btn-graph-zoom-in')?.addEventListener('click', () => {
        svg.transition().call(zoom.scaleBy, 1.3);
    });
    document.getElementById('btn-graph-zoom-out')?.addEventListener('click', () => {
        svg.transition().call(zoom.scaleBy, 0.7);
    });
    document.getElementById('btn-graph-reset')?.addEventListener('click', () => {
        svg.transition().call(zoom.transform, d3.zoomIdentity.translate(width / 2, height / 2).scale(0.8));
    });
}

// ── Helpers ──────────────────────────────────────

async function restoreGraphUI(container) {
    // Rebuild the filter panel + controls that were removed by innerHTML = ''
    const panel = document.getElementById('graph-filter-panel');
    const controls = container.querySelector('.graph-controls');

    // If they were removed, re-append from document (they're still in DOM
    // unless container.innerHTML was set to ''). We need to re-create them.
    // Since renderGraph clears the container, we need to re-inject.
    const filterHTML = `
        <div class="graph-filter-panel ${filterState.tags.length || filterState.folders.length ? '' : 'collapsed'}" id="graph-filter-panel">
            <div class="graph-filter-header">
                <span>Filters</span>
                <button id="btn-close-graph-filter" title="Close filter panel">
                    <i data-lucide="x" style="width:14px;height:14px"></i>
                </button>
            </div>
            <div class="graph-filter-section">
                <label>Tags</label>
                <div class="graph-filter-tags" id="graph-filter-tags"></div>
            </div>
            <div class="graph-filter-section">
                <label>Folder</label>
                <select class="graph-filter-select" id="graph-filter-folder">
                    <option value="">All folders</option>
                </select>
            </div>
            <div class="graph-filter-section">
                <label>Depth (hops): <span id="graph-filter-depth-val">${filterState.depth}</span></label>
                <input type="range" class="graph-filter-range" id="graph-filter-depth" min="0" max="3" value="${filterState.depth}">
            </div>
            <div class="graph-filter-actions">
                <button class="graph-filter-btn secondary" id="btn-graph-filter-reset">Reset</button>
                <button class="graph-filter-btn primary" id="btn-graph-filter-apply">Apply</button>
            </div>
        </div>
        <div class="graph-controls">
            <button class="icon-btn" id="btn-graph-filter-toggle" title="Toggle filter panel">
                <i data-lucide="filter"></i>
            </button>
            <button class="icon-btn" id="btn-graph-zoom-in" title="Zoom in">
                <i data-lucide="zoom-in"></i>
            </button>
            <button class="icon-btn" id="btn-graph-zoom-out" title="Zoom out">
                <i data-lucide="zoom-out"></i>
            </button>
            <button class="icon-btn" id="btn-graph-reset" title="Reset view">
                <i data-lucide="maximize-2"></i>
            </button>
        </div>
    `;
    container.insertAdjacentHTML('afterbegin', filterHTML);

    // Re-bind events
    initFilterPanel();
    await loadFilterOptions();

    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function dragStarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragEnded(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

export function destroyGraph() {
    if (simulation) {
        simulation.stop();
        simulation = null;
    }
}
