# DESIGN — UI Layout & Interaction

> **Phase:** 2-5 (progressive enhancement)
> **Depends on:** Phase 1 base UI
> **Files affected:** `index.html`, `app.js`, multiple `*.js` + `*.css`

---

## 1. Tổng quan

UI phát triển theo phases. Design này mô tả layout cuối cùng cho tất cả features.

---

## 2. Layout: 4-Panel Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Toolbar                                                      │
├──────────┬────────────────────────┬──────────┬───────────────┤
│          │                        │          │               │
│ Sidebar  │   Editor / Preview     │  AI Chat │  Graph/Search │
│ (240px)  │   (flexible)           │  (350px) │  (350px)      │
│          │                        │          │               │
│ • Notes  │   Markdown editing     │  Chat    │  Force graph  │
│ • Inbox  │   Split preview        │  History │  Search       │
│ • Tags   │                        │  Sources │  Related      │
│ • Tree   │                        │          │               │
├──────────┴────────────────────────┴──────────┴───────────────┤
│  Status Bar                                                   │
└──────────────────────────────────────────────────────────────┘
```

### 2.1 Responsive Behavior

```
Desktop (>1400px): 4 panels visible
Laptop (1024-1400px): 3 panels (collapse graph OR chat)
Tablet/narrow: 2 panels (sidebar + editor)
Mobile: 1 panel (full editor / sidebar dropdown)
```

### 2.2 Panel Toggle System

Mỗi panel có toggle button + keyboard shortcut:

| Panel | Shortcut | Default |
|-------|----------|---------|
| Sidebar | `Ctrl+B` | Visible |
| AI Chat | `Ctrl+Shift+A` | Hidden |
| Graph/Search | `Ctrl+Shift+G` | Hidden |
| Preview | `Ctrl+Shift+P` | Toggle |

---

## 3. Sidebar Redesign

### 3.1 Tab Navigation

```
[📝 Notes] [📥 Inbox] [🏷️ Tags] [📂 Tree]
```

### 3.2 Notes Tab (hiện tại)

```
┌─────────────────────┐
│ 🔍 Search...        │
├─────────────────────┤
│  Recent Notes        │
│  ├─ RAG Pipeline     │
│  ├─ Vector Search    │
│  └─ Today's Daily    │
│                      │
│  All Notes (142)     │
│  ├─ rag-pipeline.md  │
│  ├─ vector-search.md │
│  └─ ...              │
└─────────────────────┘
```

### 3.3 Inbox Tab (Phase 2)

```
┌─────────────────────┐
│ 📥 Inbox (5 new)    │
├─────────────────────┤
│ Today — Mar 8        │
│ ┌───────────────────┐│
│ │ 🔗 14:21          ││
│ │ "RAG pipeline     ││
│ │  article"         ││
│ │ https://examp...  ││
│ │ [Convert][Archive]││
│ └───────────────────┘│
│ ┌───────────────────┐│
│ │ � 18:30          ││
│ │ "Động lực không   ││
│ │  đến từ..."       ││
│ │ [Convert][Archive]││
│ └───────────────────┘│
│                      │
│ Yesterday — Mar 7    │
│ ├─ 3 entries         │
└─────────────────────┘
```

### 3.4 Tags Tab (existing, enhanced)

```
┌─────────────────────┐
│ 🏷️ Tags             │
├─────────────────────┤
│ ai (23)              │
│ backend (18)         │
│ python (15)          │
│ rag (8)              │
│ ───────────────      │
│ Low-connected (3)    │
│ ├─ orphan-note.md    │
│ ├─ random-idea.md    │
│ └─ old-draft.md      │
└─────────────────────┘
```

> **Per chot.md:** "Low-connected notes" thay knowledge gap detection.

### 3.5 Tree Tab (folder browser)

```
┌─────────────────────┐
│ 📂 Vault             │
├─────────────────────┤
│ ▼ ai/                │
│   ├─ rag-pipeline.md │
│   ├─ vector.md       │
│   └─ reasoning.md    │
│ ▶ backend/           │
│ ▶ daily/             │
│ ▶ inbox/             │
│ ▶ memory/            │
└─────────────────────┘
```

---

## 4. Editor Area

### 4.1 Editor Modes

```
[Edit] [Preview] [Split]
```

| Mode | Layout |
|------|--------|
| Edit | Full CodeMirror editor |
| Preview | Full rendered markdown |
| Split | 50/50 side-by-side |

### 4.2 Editor Features

- Inline wiki-link autocompletion: type `[[` → dropdown
- Slash command menu: `/` → template/block insert
- Toolbar: bold, italic, heading, code, link
- Frontmatter editor (collapsible YAML block)

### 4.3 Related Notes Block (Phase 3)

Shown below editor:

```
┌─────────────────────────────────────┐
│ 🔗 Related Notes                     │
│ ├─ vector-search.md (score: 0.85)   │
│ ├─ claude-reasoning.md (score: 0.72)│
│ └─ embeddings.md (score: 0.68)      │
│                                      │
│ 💡 Suggested links:                  │
│ ├─ [[transformer-architecture]]      │
│ └─ [[attention-mechanism]]           │
└─────────────────────────────────────┘
```

> **Per chot.md:** Auto-link suggestion ở đây, không phải tag suggestion.

---

## 5. AI Chat Panel

### 5.1 Layout

```
┌─────────────────────────┐
│ 🤖 AI Chat    [☰][✕]   │
├─────────────────────────┤
│                          │
│ 🤖 Welcome! Ask me about│
│    your knowledge vault. │
│                          │
│ ┌─────────────────────┐ │
│ │ User: How does RAG  │ │
│ │ work?               │ │
│ └─────────────────────┘ │
│                          │
│ 🤖 RAG gồm 3 bước...   │
│                          │
│ Sources:                 │
│ [ai/rag.md]             │
│ [ai/vector-search.md]   │
│                          │
├─────────────────────────┤
│ [📎] Type message...  [→]│
├─────────────────────────┤
│ Mode: [Chat][Summary]   │
│       [Explore][Links]  │
└─────────────────────────┘
```

### 5.2 Chat Modes

| Mode | Behavior |
|------|----------|
| Chat | RAG Q&A about vault |
| Summary | Summarize current note |
| Explore | "What do I know about {topic}?" |
| Links | Auto-suggest links for current note |

### 5.3 Source Interaction

Click source → open note in editor.
Hover source → preview snippet.

### 5.4 SSE Integration

```javascript
// frontend/js/chat.js

async function sendMessage(question) {
    const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ question }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let aiMessage = '';

    while (true) {
        const {done, value} = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                if (data.token) {
                    aiMessage += data.token;
                    updateChatUI(aiMessage);
                }
                if (data.done) {
                    displaySources(data.sources);
                }
            }
        }
    }
}
```

---

## 6. Graph Panel

### 6.1 Current State

D3.js force-directed graph exists. Enhance with:

### 6.2 Enhancements

```
┌─────────────────────────┐
│ 🕸️ Graph           [⚙] │
├─────────────────────────┤
│                          │
│   ┌───┐   ┌───┐        │
│   │RAG├───┤Vec│        │
│   └─┬─┘   └───┘        │
│     │                    │
│   ┌─┴─┐   ┌───┐        │
│   │LLM├───┤EMB│        │
│   └───┘   └───┘        │
│                          │
├─────────────────────────┤
│ Depth: [1] [2] [3]      │
│ Filter: [ai][backend]   │
│ Highlight: RAG sources   │
└─────────────────────────┘
```

### 6.3 AI-Graph Integration

Khi AI trả lời, highlight các notes được sử dụng trên graph:

```javascript
function highlightRAGSources(notePaths) {
    // Reset all nodes
    d3.selectAll('.node').classed('rag-source', false);

    // Highlight sources
    notePaths.forEach(path => {
        d3.selectAll('.node')
            .filter(d => d.id === path)
            .classed('rag-source', true);
    });
}
```

CSS:
```css
.node.rag-source circle {
    stroke: var(--accent-gold);
    stroke-width: 3px;
    filter: drop-shadow(0 0 4px var(--accent-gold));
}
```

---

## 7. Quick Capture (Global)

Float button or keyboard shortcut `Ctrl+Shift+C`:

```
┌─────────────────────────────┐
│ ✏️ Quick Capture             │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │ Type or paste...        │ │
│ │                         │ │
│ │                         │ │
│ └─────────────────────────┘ │
│                              │
│ 🔗 URL: [paste URL here]    │
│                              │
│ [Cancel]          [Capture]  │
└─────────────────────────────┘
```

---

## 8. Search (Command Palette Style)

`Ctrl+K` opens search:

```
┌─────────────────────────────────────────┐
│ 🔍 Search notes...                       │
├─────────────────────────────────────────┤
│ Mode: [All][Notes][Tags][Full-text]      │
├─────────────────────────────────────────┤
│ ┌──────────────────────────────────────┐ │
│ │ 📝 RAG Pipeline        ai/rag.md    │ │
│ │ 📝 Vector Search       ai/vector.md │ │
│ │ 🏷️ #rag (8 notes)                  │ │
│ └──────────────────────────────────────┘ │
│ Press Enter to open, Esc to close        │
└─────────────────────────────────────────┘
```

---

## 9. Research Threads UI (Phase 5)

### 9.1 Thread Selector

```
┌─────────────────────────────┐
│ 🔬 Research Threads          │
├─────────────────────────────┤
│ Active:                      │
│ ├─ "RAG Pipeline Design"    │
│ │   3 notes · 5 messages    │
│ ├─ "System Design"          │
│ │   7 notes · 12 messages   │
│                              │
│ [+ New Thread]               │
└─────────────────────────────┘
```

### 9.2 Thread View

```
Thread: RAG Pipeline Design

📝 Explored notes:
  ai/rag.md
  ai/vector-search.md
  ai/chunking.md

💬 Key insights:
  - Hybrid search > pure vector
  - Graph expansion adds related context
  - 2000 token context limit sufficient

[Continue researching] [Export to note]
```

---

## 10. Theme System

### 10.1 Variables

```css
/* frontend/css/variables.css */

:root {
    /* Light theme (default) */
    --bg-primary: #ffffff;
    --bg-secondary: #f5f5f5;
    --bg-tertiary: #eaeaea;
    --text-primary: #1a1a1a;
    --text-secondary: #565656;
    --accent-primary: #4a90d9;
    --accent-gold: #e5a100;
    --border: #e0e0e0;
}

[data-theme="dark"] {
    --bg-primary: #1e1e1e;
    --bg-secondary: #252525;
    --bg-tertiary: #2d2d2d;
    --text-primary: #d4d4d4;
    --text-secondary: #808080;
    --accent-primary: #569cd6;
    --accent-gold: #dcdcaa;
    --border: #3e3e3e;
}
```

### 10.2 Toggle

```javascript
// Ctrl+Shift+T
function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    html.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
    localStorage.setItem('theme', html.getAttribute('data-theme'));
}
```

---

## 11. Keyboard Shortcuts (Complete)

| Category | Shortcut | Action |
|----------|----------|--------|
| **Navigation** | `Ctrl+K` | Search / Command palette |
| | `Ctrl+B` | Toggle sidebar |
| | `Ctrl+Shift+A` | Toggle AI panel |
| | `Ctrl+Shift+G` | Toggle graph panel |
| **Editor** | `Ctrl+S` | Save note |
| | `Ctrl+Shift+P` | Toggle preview |
| | `Ctrl+N` | New note |
| **Capture** | `Ctrl+Shift+C` | Quick capture |
| **Inbox** | `Enter` | Convert entry |
| | `A` | Archive entry |
| | `D` | Delete entry |
| | `↑/↓` | Navigate entries |
| **AI** | `Enter` | Send message |
| | `Shift+Enter` | New line in chat |
| **Theme** | `Ctrl+Shift+T` | Toggle dark/light |

---

## 12. Phase Rollout

| Phase | UI Addition |
|-------|-------------|
| 2 | Inbox sidebar tab, Quick Capture modal, Telegram notifications |
| 3 | Related Notes block, Search mode selector (hybrid/semantic/keyword) |
| 4 | AI Chat panel, Source highlighting on graph |
| 5 | Research Threads tab, Memory panel, Low-connected notes view |
| 6 | Docker status indicator, Performance dashboard (simple) |

---

## 13. File Structure

```
frontend/
  index.html                   # Shell (add panel containers)
  css/
    variables.css              # Theme variables
    layout.css                 # 4-panel grid
    base.css
    components.css
    editor.css
    graph.css
    graph-filter.css
    toolbar.css
    template-modal.css
    chat.css                   # NEW: AI chat panel
    inbox.css                  # NEW: Inbox UI
    search-palette.css         # NEW: Command palette
  js/
    app.js                     # Panel toggle logic
    api.js                     # API wrapper
    editor.js
    graph.js
    modal.js
    preview.js
    quick-capture.js
    search.js
    shortcuts-modal.js
    sidebar.js
    slash-menu.js
    template-modal.js
    toc.js
    toolbar.js
    chat.js                    # NEW: AI chat
    inbox.js                   # NEW: Inbox
    research-threads.js        # NEW: Research threads
    search-palette.js          # NEW: Command palette
```
