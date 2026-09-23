# Phase 2 Specification: Time-Series Event Log & Explicit Timeline Editor

> ## ✅ STATUS: COMPLETE
> **Progress:** 5/5 tasks · 100% of checklist items
> **Last updated:** 2026-09-23
> **Exit gate:** `python -m pytest tests/test_phase_2.py` + `tests/test_phase_2_ui.py` — **PASSING**
> **Next step:** Phase 3 (dashboard UI, auth, LLM providers).

| Task | Title | Status |
| ---- | ----- | ------ |
| 1 | Event Log & Message Schema (Layer 3) | ✅ Done |
| 2 | Sliding-Window Memory Engine (Layer 2) | ✅ Done |
| 3 | Explicit Timeline Node CRUD (Layer 2 & 3) | ✅ Done |
| 4 | Message Conversation Management (Layer 2 & 3) | ✅ Done |
| 5 | Unit & UI Testing / Verification | ✅ Done |

## 1. Objective & Scope

- **Core Goal:** Build the agent's long-term memory as a plain chronological Line of Truth node list with transparent, explicit editing. There is no hidden or silent history-rewrite mode.
- **In-Scope Deliverables:**
  - Layer 3 SQLAlchemy models for `event_log_nodes` and `messages`, including `event_log_nodes.agent_id` as a foreign key to `agents.id`, `messages.node_id` as a foreign key to `event_log_nodes.id`, and a persistent per-node message `position` for explicit conversation ordering.
  - Layer 3 repositories supporting chronological node insertion, message association, ordering, reassignment, and guarded node deletion.
  - Layer 2 business services for adding, editing, and deleting timeline nodes.
  - Layer 2 business services for adding, editing, deleting, reordering, and moving messages between nodes.
  - Message sender/content fields and a user-editable conversation timestamp. The sender is restricted to the local user or the currently selected Agent.
  - Multi-agent timeline isolation and a dashboard agent switcher.
  - Node deletion protection: a node can be deleted only when it has zero attached messages.
  - Prompt-context cache invalidation after explicit timeline mutations.
  - Layer 1 dashboard forms and controls for all operations, with no silent or hidden edit affordance.
- **Out-of-Scope:** OAuth/Auth0 login flows, LLM provider API clients (Ollama/OpenRouter), Termux deployment, and the plugin marketplace. The existing sliding-window service remains an internal prompt-context concern; it is not the user-facing Line of Truth editor.

## 2. Technical Guardrails (Do's and Don'ts)

- **DO:** Treat every node and message change as an ordinary, visible CRUD operation.
- **DO:** Keep Layer 2 framework-independent and communicate with persistence only through repository interfaces.
- **DO:** Enforce the zero-message node-deletion rule in the business service and provide an atomic persistence guard for the concrete event repository.
- **DO:** Scope every timeline read and mutation to the selected Agent and reject cross-agent access.
- **DO:** Keep message order (`position`) independent from conversation time so users can reorder a conversation and then correct timestamps manually.
- **DO:** Preserve SQLite WAL mode and busy timeouts for concurrent background writes.
- **DON'T:** Implement silent edits, hidden edit markers, or any special mode that changes history without a visible user operation.
- **DON'T:** Delete a node that still has child messages; move or delete those messages first.
- **DON'T:** Leak SQLAlchemy sessions or raw persistence objects into Layer 2 business methods.

## 3. Implementation Tasks & Checklist

- [x] **Task 1: Event Log & Message Schema (Layer 3)**
  - [x] Define `event_log_nodes` with chronological sequence, Agent foreign key, and summary fields.
  - [x] Define `messages` with an event-node foreign key, user/selected-agent sender, content, conversation timestamp, and explicit position fields.
  - [x] Implement concrete repositories with position ordering and an upgrade path for older databases.

- [x] **Task 2: Sliding-Window Memory Engine (Layer 2)**
  - [x] Build `MemoryWindowService` to slice the internal prompt context based on the configured node limit.
  - [x] Implement token estimation and budgeting rules without changing the visible timeline list.

- [x] **Task 3: Explicit Timeline Node CRUD (Layer 2 & 3)**
  - [x] Add nodes to the selected Agent, edit their summaries, and delete only empty nodes.
  - [x] Reject cross-agent timeline reads and mutations and provide an agent switcher.
  - [x] Surface every operation in the dashboard and invalidate prompt context after changes.

- [x] **Task 4: Message Conversation Management (Layer 2 & 3)**
  - [x] Add, edit, and delete messages with a fixed User/current-Agent sender dropdown and user-selected conversation time.
  - [x] Move messages up/down within a node using persistent positions.
  - [x] Move messages to another node so a source node can become empty and be deleted.

- [x] **Task 5: Unit & UI Testing / Verification**
  - [x] Cover repository ordering, guarded deletion, business validation, and the full dashboard workflow in `tests/test_phase_2.py` and `tests/test_phase_2_ui.py`.

## 4. Exit Gate / Acceptance Test

To validate Phase 2, run:

```bash
python -m pytest tests/test_phase_2.py
python -m pytest tests/test_phase_2_ui.py
```
