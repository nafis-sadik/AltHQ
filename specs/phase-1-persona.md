## title: Phase 1 Specification

# Phase 1 Specification: Agent CRUD, Active Agent & Browse UI

> ## ✅ STATUS: COMPLETE
> **Progress:** 5/5 tasks · 100% of checklist items
> **Last updated:** 2026-09-25
> **Exit gate:** `python -m pytest tests/test_phase_1.py` + `tests/test_phase_1_ui.py` — **PASSING**
> **Next step:** Phase 2 (Line of Truth + topic detection).

| Task | Title | Status |
| ---- | ----- | ------ |
| 1 | Database & Persistence Setup (Layer 3) | ✅ Done |
| 2 | Local JSON Config Manager (Layer 3) | ✅ Done |
| 3 | Persona Business Core (Layer 2) | ✅ Done |
| 4 | Active Agent Field & Switching Logic | ✅ Done |
| 5 | Agent Browse UI & Active Selection | ✅ Done |

## 1. Objective & Scope

**- Core Goal:** Establish the data persistence layer, repositories, and business logic for managing multiple agent personas, with **one active agent at a time** and a UI to browse, select, and change the active agent.

**- In-Scope Deliverables:**
  - SQLite database initialization with WAL mode.
  - Layer 3 `Agent` model with **`is_active` boolean field** (only one agent can be active at a time).
  - Layer 3 `AgentRepository` with `set_active_async(agent_id)` that clears other active flags.
  - Layer 2 `PersonaService`: `get_active_async()`, `set_active_async()`, `list_agents_async()`, `GetByIdAsync()`.
  - Layer 1 UI: **Agent browser page** listing all personas with "Set as Active" action.
  - Layer 1 UI: Persona create/edit/detail pages.
  - Agent switcher in sidebar/header showing current active agent.

**- Out-of-Scope:** Event log, topic detection, vector memory, LLM providers, auth, Termux, marketplace.

---

## 2. Technical Guardrails

- **DO:** Enforce the 3-layer rule. `PersonaService` (Layer 2) must interact with persistence strictly through repository interfaces.
- **DO:** `set_active_async` must be atomic — clear all other `is_active=true` rows before setting the new one, or use a transaction.
- **DON'T:** Import any web framework into Layer 2 or Layer 3.
- **DON'T:** Allow more than one agent to have `is_active=true` at any time.

---

## 3. Implementation Tasks & Checklist

### Task 1: Database & Persistence Setup (Layer 3) — ✅ Already Done
- [x] SQLite engine with `PRAGMA journal_mode=WAL;` and `PRAGMA busy_timeout=5000;`.
- [x] Generic Base Repository class with CRUD.
- [x] `Agent` model: `id`, `name`, `gender`, `profile_picture`, `bio`, `background_story`, `active_node_limit`, `created_at`, `updated_at`.

### Task 2: Local JSON Config Manager (Layer 3) — ✅ Already Done
- [x] `config.json` file handler for runtime parameters.

### Task 3: Persona Business Core (Layer 2) — ✅ Already Done
- [x] `PersonaService` with `AddNewAsync`, `UpdateExistingAsync`, `GetPagedPersona`, `GetByIdAsync`, `CompilePromptSegments`.
- [x] `PersonaUpdate`, `PersonaValidationResult`, `PersonaPromptSegments` DTOs.
- [x] Validation logic in `model_validation.py`.

### Task 4: Active Agent Field & Switching Logic — ✅ Done
- [x] **Add `is_active` column to `Agent` entity** (Boolean, default=False).
- [x] **First-deployment schema:** the injected `SQLAlchemyRepository[Agent]` creates the current `agents` table directly; `AgentRepository` does not manage schema lifecycle, and legacy-table upgrades are deferred until an existing-data upgrade strategy is introduced.
- [x] **AgentRepository:** add `set_active_async(agent_id)` — delegate to the injected generic repository update operation to clear other agents' `is_active=False`, then set the target agent's `is_active=True`.
- [x] **AgentRepository:** add `get_active_async()` — return the agent with `is_active=True`, or None.
- [x] **PersonaService:** add `get_active_async()` — delegate to repository.
- [x] **PersonaService:** add `set_active_async(agent_id)` — delegate to repository.
- [x] **PersonaService:** add `list_agents_async()` — return all agents sorted by name.
- [x] **PersonaService:** update `GetByIdAsync(None)` to resolve to the active agent (not return None).

### Task 5: Agent Browse UI & Active Selection — ✅ Done
- [x] **Layer 1 route:** `GET /agents/` — list all agents with name, bio snippet, active badge, "Set as Active" button.
- [x] **Layer 1 route:** `POST /api/agents/<id>/set_active/` — call `PersonaService.set_active_async()`.
- [x] **Sidebar/header:** show current active agent name; changing the switcher persists the active agent.
- [x] **Persona create/edit pages:** unchanged, but new agents are inactive until explicitly selected.
- [x] **Event log controller:** uses `get_active_async()` when no `agent_id` is specified (replaces alphabetical-first fallback).

---

## 4. Exit Gate / Acceptance Test

```bash
python -m pytest tests/test_phase_1.py
python -m pytest tests/test_phase_1_ui.py
```

**Acceptance criteria:**
- `Agent` table has `is_active` column.
- Only one agent can be active at a time (enforced at DB/service level).
- `GET /agents/` shows all personas with active indicator.
- "Set as Active" works and immediately reflects in the UI.
- When no `agent_id` is specified, operations use the active agent.
