# Phase 2 Specification: Time-Series Event Log & God-Mode Editor

## 1. Objective & Scope
- **Core Goal:** Build the agent's long-term memory system using a time-series event graph ("line of truth"), sliding-window token management, and the silent "God-Mode" editing framework that allows users to rewrite historical reality without audit trails.
- **In-Scope Deliverables:**
  - Layer 3 SQLAlchemy models for `event_log_nodes` and `messages` (linked parent-child dialogue and timeline states).
  - Layer 3 repositories supporting chronological node insertion, sliding-window queries, and message association.
  - Layer 2 Business Service (`EventLogManager`) implementing fixed max active node size truncation and dynamic prompt token budgeting.
  - Layer 2 "God-Mode" update logic to modify past nodes/messages silently in the database without generating audit entries or system edit flags.
  - Cache-invalidation hooks that trigger immediate prompt recompilation when historical nodes are altered.
- **Out-of-Scope:** Web UI dashboard rendering, Auth0 login flows, LLM provider API clients (Ollama/OpenRouter), and Termux mobile deployment daemonization.

---

## 2. Technical Guardrails (Do's and Don'ts)
- **DO:** Ensure that God-Mode updates directly execute database persistence updates via Layer 3 repositories without writing any logging or audit tracking rows.
- **DO:** Respect the user-configured sliding window node limit strictly in Layer 2 memory management. Older historical nodes remain preserved in storage but are excluded from active context prompts unless retrieved via vector query layers.
- **DON'T:** Leak database sessions or raw SQLAlchemy objects into Layer 2 business logic methods.

---

## 3. Implementation Tasks & Checklist

- [ ] **Task 1: Event Log & Message Schema (Layer 3)**
  - [ ] Define SQLAlchemy model for `event_log_nodes` (fields: `id`, `agent_id`, `sequence_index`, `summary`, `timestamp`, `is_active`).
  - [ ] Define SQLAlchemy model for `messages` (fields: `id`, `node_id`, `sender`, `content`, `timestamp`).
  - [ ] Implement concrete repositories `EventLogRepository` and `MessageRepository`.

- [ ] **Task 2: Sliding-Window Memory Engine (Layer 2)**
  - [ ] Build `MemoryWindowService` to slice active event nodes based on the user-configured prompt window size.
  - [ ] Implement token estimation and budgeting rules to separate active sliding nodes from archived history.

- [ ] **Task 3: God-Mode Stealth Editor & Cache Invalidation (Layer 2 & 3)**
  - [ ] Implement silent update methods that alter historical node summaries or messages without generating audit logs.
  - [ ] Build an observer/callback cache invalidation trigger that forces prompt recompilation on the next execution loop when an edit occurs.

- [ ] **Task 4: Unit Testing & Verification**
  - [ ] Write a standalone test script (`tests/test_phase_2.py`) simulating a growing timeline, verifying sliding window truncation, testing a silent God-Mode edit, and confirming prompt cache invalidation.

---

## 4. Exit Gate / Acceptance Test
To declare **Phase 2 Complete**, run the validation test suite:
```bash
python -m pytest tests/test_phase_2.py