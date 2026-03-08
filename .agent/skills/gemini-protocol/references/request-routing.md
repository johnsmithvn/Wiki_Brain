# Request Routing Matrix

Use this matrix before any implementation.

## Request Classification

| Request Type | Typical Triggers | Active Scope | Required Action |
| --- | --- | --- | --- |
| QUESTION | "what is", "how does", "explain" | Tier 0 | Answer directly |
| SURVEY/INTEL | "analyze", "list files", "overview" | Tier 0 + Explorer | Inspect and report, no implementation |
| SIMPLE CODE | single-file fix/add/change | Tier 0 + Tier 1 (lite) | Implement focused edit |
| COMPLEX CODE | "build", "create", "implement", "refactor" | Tier 0 + Tier 1 (full) + Agent | Ask gate questions, then implement |
| DESIGN/UI | "design", "dashboard", "page", "UI" | Tier 0 + Tier 1 + Agent | Apply design agent rules, then implement |
| SLASH CMD | `/create`, `/orchestrate`, `/debug` | Command workflow | Follow matching workflow doc |

## Agent Selection Rules

1. Respect explicit user override when `@agent` is named.
2. Route mobile requests to `mobile-developer`.
3. Route single-domain coding tasks to domain specialist:
   - Web UI -> `frontend-specialist`
   - API/backend -> `backend-specialist`
   - Security -> `security-auditor`
   - Debugging -> `debugger`
   - Testing -> `test-engineer`
4. Route multi-domain or ambiguous complex work to `orchestrator`.

## Mandatory Pre-Execution Checklist

1. Read `.agent/rules/GEMINI.md`.
2. Read target agent file in `.agent/agents/`.
3. Load required skills from agent frontmatter.
4. Enforce Socratic gate when complexity/risk is non-trivial.
5. Confirm dependency impact before editing files.
