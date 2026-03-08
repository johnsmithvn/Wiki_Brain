# PLAN-ai-knowledge-os

## Overview
Xây dựng **AI Knowledge OS** dựa trên codebase `second-brain` hiện tại theo lộ trình 5 phase, ưu tiên hoàn thiện **Phase 1 (Solid Knowledge Base)** để tạo nền ổn định trước khi thêm semantic layer, AI reasoning, workspace database và hạ tầng AI production.

Mục tiêu của plan này:
- Chốt backlog triển khai theo thứ tự phụ thuộc kỹ thuật.
- Chia nhiệm vụ rõ ràng theo backend/frontend/infra.
- Định nghĩa tiêu chí kiểm chứng để tránh “xong tính năng nhưng chưa chạy ổn định”.

## Project Type
- **WEB + BACKEND (FastAPI + Vanilla JS)**

## Success Criteria
- Phase 1 hoàn thành với 4 năng lực cốt lõi:
  - Popup chọn template khi tạo note mới (phím tắt theo spec).
  - Tự động reindex khi file thay đổi từ bên ngoài app.
  - Graph có bộ lọc tag/folder/depth hoạt động đúng.
  - Rename note tự cập nhật toàn bộ `[[wiki-links]]` liên quan.
- Kiến trúc sẵn sàng để mở rộng sang Phase 2-5 mà không cần rewrite lớn.
- Có checklist verification + tiêu chí đo chất lượng cho mỗi phase.

## Tech Stack (Current + Planned)
- Current:
  - Backend: FastAPI, aiofiles
  - Search: SQLite FTS5
  - Frontend: Vanilla JS (ES modules), D3
  - Storage: Markdown filesystem
- Planned additions:
  - Phase 2: Embedding model (BGE-small/Nomic), Qdrant
  - Phase 3: Ollama + local LLM, Neo4j
  - Phase 5: Celery/Redis (hoặc Dramatiq), observability + RAG evaluation

## File Structure Impact
- Backend
  - `second-brain/backend/api/notes.py`
  - `second-brain/backend/api/graph.py`
  - `second-brain/backend/main.py`
  - `second-brain/backend/services/file_service.py`
  - `second-brain/backend/services/index_service.py`
  - `second-brain/backend/services/link_service.py`
  - (new) `second-brain/backend/services/template_service.py`
  - (new) `second-brain/backend/services/watcher_service.py`
- Frontend
  - `second-brain/frontend/index.html`
  - `second-brain/frontend/js/app.js`
  - `second-brain/frontend/js/sidebar.js`
  - `second-brain/frontend/js/api.js`
  - `second-brain/frontend/js/graph.js`
  - (new) `second-brain/frontend/js/template-modal.js`
  - (new) `second-brain/frontend/css/template-modal.css`
- Vault conventions
  - `second-brain/knowledge/template/` (template notes)

## Task Breakdown

### Phase 1 — Solid Knowledge Base (Execution Now)

- [ ] **T01: Baseline + dependency hardening**
  - Agent: `backend-specialist`
  - Skill: `clean-code`
  - Priority: P0
  - Dependencies: none
  - INPUT → OUTPUT → VERIFY:
    - Input: codebase hiện tại + requirements
    - Output: baseline matrix (feature hiện có/chưa có), requirements update (`watchdog`)
    - Verify: app khởi động bình thường, không regression endpoint hiện hữu

- [ ] **T02: Template discovery API + model**
  - Agent: `backend-specialist`
  - Skill: `api-patterns`
  - Priority: P0
  - Dependencies: T01
  - INPUT → OUTPUT → VERIFY:
    - Input: folder `knowledge/template/`
    - Output: API trả danh sách template + API đọc template content
    - Verify: gọi API trả đúng metadata/template content; lỗi path traversal bị chặn

- [ ] **T03: New note flow with template chooser UI**
  - Agent: `frontend-specialist`
  - Skill: `frontend-design`
  - Priority: P1
  - Dependencies: T02
  - INPUT → OUTPUT → VERIFY:
    - Input: shortcut create note + template APIs
    - Output: popup chọn template, tạo note mới từ template, fallback “blank note”
    - Verify: thao tác keyboard tạo note đúng nội dung template và mở note mới thành công

- [ ] **T04: File watcher + auto-reindex pipeline hook**
  - Agent: `backend-specialist`
  - Skill: `python-patterns`
  - Priority: P0
  - Dependencies: T01
  - INPUT → OUTPUT → VERIFY:
    - Input: thay đổi file ngoài app (create/update/delete/rename)
    - Output: watcher service phát hiện thay đổi và gọi update index/tags/links
    - Verify: sửa file bằng VS Code hoặc git checkout/pull thì search/tag/backlink cập nhật sau debounce

- [ ] **T05: Rename propagation for `[[wiki-links]]`**
  - Agent: `backend-specialist`
  - Skill: `clean-code`
  - Priority: P0
  - Dependencies: T04
  - INPUT → OUTPUT → VERIFY:
    - Input: rename note A -> B
    - Output: tất cả note tham chiếu `[[A]]`/`[[A|alias]]` được rewrite sang `[[B]]` giữ alias hợp lệ
    - Verify: rename 1 note có nhiều backlink, mở từng note kiểm tra link đã đổi và graph không đứt cạnh

- [ ] **T06: Advanced graph filter API**
  - Agent: `backend-specialist`
  - Skill: `api-patterns`
  - Priority: P1
  - Dependencies: T04
  - INPUT → OUTPUT → VERIFY:
    - Input: filter params `tags[]`, `folders[]`, `depth`
    - Output: API graph trả node/edge đã lọc
    - Verify: query filter trả đúng subset, không crash khi filter rỗng

- [ ] **T07: Graph filter controls in UI**
  - Agent: `frontend-specialist`
  - Skill: `frontend-design`
  - Priority: P1
  - Dependencies: T06
  - INPUT → OUTPUT → VERIFY:
    - Input: graph filter API
    - Output: panel filter + apply/reset + sync state với graph render
    - Verify: chọn tag/folder/depth thay đổi graph theo thời gian thực, reset về full graph được

- [ ] **T08: Phase 1 integration test + changelog/release note**
  - Agent: `test-engineer`
  - Skill: `testing-patterns`
  - Priority: P0
  - Dependencies: T03, T05, T07
  - INPUT → OUTPUT → VERIFY:
    - Input: toàn bộ thay đổi Phase 1
    - Output: test checklist manual + smoke automation; cập nhật CHANGELOG
    - Verify: test pass trên các luồng create/edit/rename/search/graph và không phát sinh bug blocker

### Phase 2 — AI Search Layer (Design + Build After Phase 1)

- [ ] **T09: Semantic index architecture decision (chunking + embedding schema)**
  - Agent: `backend-specialist`
  - Skill: `architecture`
  - Priority: P1
  - Dependencies: T08
  - INPUT → OUTPUT → VERIFY:
    - Input: notes corpus + search requirements
    - Output: decision record cho chunking, embedding model, Qdrant collection schema
    - Verify: có benchmark plan (quality + latency) và migration path từ FTS hiện tại

- [ ] **T10: Implement semantic retrieval + related notes block + link suggestion baseline**
  - Agent: `backend-specialist` + `frontend-specialist`
  - Skill: `api-patterns`, `frontend-design`
  - Priority: P1
  - Dependencies: T09
  - INPUT → OUTPUT → VERIFY:
    - Input: embedding pipeline + vector DB
    - Output: semantic search endpoint, related-notes UI block, suggestion API
    - Verify: cùng query nhưng semantic search trả kết quả đúng ngữ nghĩa hơn keyword-only

### Phase 3 — AI Brain

- [ ] **T11: RAG chat (`Ask Your Vault`) with source-grounded answers**
  - Agent: `backend-specialist`
  - Skill: `api-patterns`
  - Priority: P2
  - Dependencies: T10
  - INPUT → OUTPUT → VERIFY:
    - Input: semantic retrieval context + Ollama LLM
    - Output: chat API + citation/source references
    - Verify: câu trả lời có trích nguồn note nội bộ, giảm hallucination theo checklist

- [ ] **T12: Knowledge graph reasoning + weekly synthesis jobs**
  - Agent: `backend-specialist`
  - Skill: `architecture`
  - Priority: P2
  - Dependencies: T11
  - INPUT → OUTPUT → VERIFY:
    - Input: entities/relations + scheduler
    - Output: Neo4j pipeline + weekly summary generation job
    - Verify: summary tuần có chủ đề chính, liên kết được tới notes gốc

### Phase 4 — Intelligent Workspace

- [ ] **T13: Structured pages (table/properties/query) foundation**
  - Agent: `backend-specialist` + `frontend-specialist`
  - Skill: `database-design`, `frontend-design`
  - Priority: P2
  - Dependencies: T12
  - INPUT → OUTPUT → VERIFY:
    - Input: page schema + property model
    - Output: database-like pages + query layer + list/kanban views
    - Verify: tạo dự án/task với properties và lọc/nhóm trong UI thành công

### Phase 5 — AI System Infrastructure

- [ ] **T14: Async worker + unified indexing pipeline + observability/eval/caching**
  - Agent: `devops-engineer` + `backend-specialist`
  - Skill: `deployment-procedures`, `architecture`
  - Priority: P0 (khi bắt đầu scale AI workloads)
  - Dependencies: T11
  - INPUT → OUTPUT → VERIFY:
    - Input: các job nặng (embedding, graph extraction, rerank)
    - Output: queue worker, telemetry, RAG eval loop, cache strategy
    - Verify: API response time ổn định khi ingest lớn, có metrics dashboard + báo cáo eval định kỳ

## Agent Assignments
- `project-planner`: quản lý dependency + update plan mỗi sprint.
- `backend-specialist`: toàn bộ service/API/index/retrieval/worker integration.
- `frontend-specialist`: modal template, graph filter UI, related-notes, workspace views.
- `test-engineer`: test matrix + regression guardrails cho CRUD/search/graph/RAG.
- `devops-engineer`: queue, observability, deployment reliability.

## Risks & Mitigation
- Rủi ro race condition khi watcher + API update cùng lúc.
  - Mitigation: debounce + idempotent index update + per-path lock.
- Rủi ro rename link rewrite sai alias hoặc context code block.
  - Mitigation: parser-based rewrite thay vì regex thay thế thô.
- Rủi ro chi phí/độ trễ khi vào Phase 2-3.
  - Mitigation: batch embedding, cache, async queue, evaluation loop sớm từ Phase 5.

## Phase X — Verification Checklist
- [ ] Security scan (không lộ secrets, không path traversal regression).
- [ ] Lint/type/test pass cho backend/frontend.
- [ ] Manual flow pass:
  - [ ] Create note từ template
  - [ ] External file change auto-reindex
  - [ ] Rename note auto-update wiki links toàn vault
  - [ ] Graph filter theo tags/folders/depth
- [ ] Performance smoke:
  - [ ] Startup index không tăng lỗi
  - [ ] Search/graph response time chấp nhận được với vault mẫu
- [ ] Cập nhật `second-brain/CHANGELOG.md` theo mốc phase/sprint.

## Immediate Sprint Recommendation
- Sprint 1 (1-2 tuần): **T01, T02, T03, T04**
- Sprint 2 (1 tuần): **T05, T06, T07, T08**
- Sau Sprint 2: review chất lượng rồi mới mở T09 (Semantic layer)
