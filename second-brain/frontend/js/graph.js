// ============================================
// Graph View - D3.js Force-Directed
// ============================================

import { api } from './api.js';

let simulation = null;
let svg = null;
let zoom = null;
let onNodeClick = null;

export function initGraph({ onClick }) {
    onNodeClick = onClick;
}

export async function renderGraph(container, focusPath = null) {
    container.innerHTML = '';

    let data;
    try {
        data = focusPath
            ? await api.getLocalGraph(focusPath, 2)
            : await api.getGraph();
    } catch (e) {
        container.innerHTML = `<div class="empty-state"><p>Failed to load graph</p></div>`;
        return;
    }

    if (!data.nodes.length) {
        container.innerHTML = `<div class="empty-state">
            <i data-lucide="git-branch" style="width:48px;height:48px;opacity:0.3"></i>
            <h3>No connections yet</h3>
            <p>Create notes with [[wiki-links]] to see the graph</p>
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

    // Center initially
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
        .attr('fill', d => d.group === 'center' ? 'var(--accent)' : 'var(--bg-active)')
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
