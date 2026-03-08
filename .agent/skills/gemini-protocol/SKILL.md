---
name: gemini-protocol
description: Governance workflow for Antigravity Kit execution. Use when handling requests in this workspace that require GEMINI-aligned request classification, agent routing, Socratic gate checks, and verification flow based on `.agent/rules/GEMINI.md`.
---

# Gemini Protocol

## Overview

Apply a consistent execution protocol for tasks governed by `GEMINI.md`.
Classify the request, select the right agent and skills, enforce gate checks, then execute and verify.

## Workflow

1. Read `.agent/rules/GEMINI.md`.
2. Read `.agent/ARCHITECTURE.md` for system map.
3. Classify the request type using `references/request-routing.md`.
4. Pick the primary agent (or `orchestrator` for multi-domain work).
5. Read the chosen agent file in `.agent/agents/`.
6. Load only required skill docs from the agent's `skills:` frontmatter.
7. Apply Socratic gate before implementation for complex or unclear work.
8. Execute edits with dependency awareness.
9. Run verification relevant to the change and report outcomes.

## Rule Priority

- Apply precedence strictly:
  1. `GEMINI.md` (global rules)
  2. Agent file in `.agent/agents/*.md`
  3. Skill file(s) in `.agent/skills/*/SKILL.md`

If rules conflict, follow the higher-priority source and note the override.

## Agent Routing Rules

- Respect explicit user override when user names an `@agent`.
- Route mobile work to `mobile-developer` (not `frontend-specialist`).
- Route multi-domain or high-complexity work to `orchestrator`.
- For direct factual questions, respond directly when no specialist behavior is required.
- Announce which expertise is applied before specialized execution.

Announcement template:

```markdown
Applying knowledge of `@[agent-name]`...
```

## Socratic Gate

Before implementation, ask discovery questions when:
- The task is a new feature, structural refactor, orchestration request, or ambiguous request.
- The request includes major tradeoffs, edge cases, or unclear scope.

Minimum gate behavior:
- New feature/build: ask at least 3 strategic questions.
- Code edit/bug fix: confirm impact surface and constraints.
- User says "proceed": still ask edge-case questions when risk remains.

Do not start implementation until gate questions are resolved.

## File Dependency Awareness

Before modifying files:
1. Check dependency mapping in `CODEBASE.md` if available.
2. Identify impacted files (imports/callers/schemas/contracts).
3. Update dependent files in the same change when needed.

## Verification Protocol

Trigger full checks when user asks for "final checks", "run all tests", or equivalent.

Standard commands:

```bash
python .agent/scripts/checklist.py .
python .agent/scripts/checklist.py . --url <URL>
```

Prioritize fix order:
1. Security
2. Lint
3. Schema
4. Tests
5. UX
6. SEO
7. Performance/E2E

## References

- Request classifier and routing matrix: `references/request-routing.md`
- Global rule source of truth: `.agent/rules/GEMINI.md`

## Completion Criteria

Mark work complete only when:
- Correct request class and agent routing were applied.
- Required gate questions were asked when needed.
- Implementation and dependent updates are finished.
- Verification results were run or explicitly reported as skipped/blocked.
