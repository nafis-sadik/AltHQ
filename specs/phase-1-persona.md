## title: Phase 1 Specification

# Phase 1 Specification: Persona Engine & Profile Management

## 1. Objective & Scope
- **Core Goal:** Establish the data persistence layer, SQLAlchemy models, generic repositories, and framework-independent business logic for managing the agent's identity, metadata, character sheet, and local runtime configuration.
- **In-Scope Deliverables:**
  - SQLite database initialization with Write-Ahead Logging (`WAL` mode) enabled.
  - Layer 3 Generic Repository base class and concrete `AgentRepository`.
  - Layer 3 database models (`Agent` table for name, gender, profile picture URL/path, bio, background story, and active prompt token limits).
  - Raw JSON configuration manager (`config.json`) for lightweight runtime parameters.
  - Layer 2 Business Service (`PersonaManager`) implementing pure Python state manipulation following SOLID principles.
- **Out-of-Scope:** Flask/FastAPI web controllers, dashboard HTML views, OAuth auth, LLM provider API integration, and the time-series event log (reserved for Phase 2).

---

## 2. Technical Guardrails (Do's and Don'ts)
- **DO:** Enforce the 3-layer rule. `PersonaManager` (Layer 2) must interact with database persistence strictly through repository interfaces passed via Dependency Injection.
- **DO:** Initialize SQLite with explicit WAL mode and busy timeouts to prevent concurrency locking errors during background agent loops.
- **DON'T:** Import any web framework modules (Flask, FastAPI) or presentation objects into Layer 2 or Layer 3 source files.

---

## 3. Implementation Tasks & Checklist

- [x] **Task 1: Database & Persistence Setup (Layer 3)**
  - [x] Implement SQLite engine initializer with `PRAGMA journal_mode=WAL;` and `PRAGMA busy_timeout=5000;`.
  - [x] Create the Generic Base Repository class supporting standard CRUD (`get_by_id`, `add`, `update`, `delete`).
  - [x] Define SQLAlchemy model for `agents` (fields: `id`, `name`, `gender`, `profile_picture`, `bio`, `background_story`, `active_node_limit`, `created_at`, `updated_at`).

- [x] **Task 2: Local JSON Config Manager (Layer 3)**
  - [x] Build a robust file handler utility to read/write default local settings to `config.json`.

- [x] **Task 3: Persona Business Core (Layer 2)**
  - [x] Implement `PersonaService` class in pure Python (framework-agnostic).
  - [x] Write methods to update character metadata, validate bio constraints, and compile base persona prompt segments.

- [x] **Task 4: Unit Testing & Verification**
  - [x] Write a standalone test script (`tests/test_phase_1.py`) validating repository CRUD operations and persona state serialization without launching a web server.

---

## 4. Exit Gate / Acceptance Test
To declare **Phase 1 Complete**, run the validation test suite:
```bash
python -m pytest tests/test_phase_1.py