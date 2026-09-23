# System Architecture Specification: Autonomous Personal AI Agent

## 1. High-Level System Overview
This document defines the structural architecture, data flow, component boundaries, and persistence models for the Autonomous Personal AI Agent framework. The system is designed to operate locally on desktop environments (`venv` via Windows/Linux) and natively on mobile hardware (**Termux on Android**), featuring a server-side rendered dashboard and long-term memory management.

---

## 2. The Three-Layer Clean Architecture
The codebase strictly adheres to a 3-layer architecture to decouple business logic from infrastructure frameworks, preventing framework lock-in and ensuring high testability.

```text
┌────────────────────────────────────────────────────────┐
│               LAYER 1: APPLICATION LAYER               │
│      (`src/app (layer # 1)/`: Controllers, Web Routing,│
│       Bootstrap 5 UI Views & jQuery Interactions)      │
└──────────────────────────┬─────────────────────────────┘
                           │ HTTP / Service Calls
                           ▼
┌────────────────────────────────────────────────────────┐
│               LAYER 2: BUSINESS LAYER                  │
│     (`src/business (layer # 2)/`: Framework-Independent│
│      Core, Persona Engine, Sliding-Window Memory, Prompts)│
└──────────────────────────┬─────────────────────────────┘
                           │ Repository Interfaces / DI
                           ▼
┌────────────────────────────────────────────────────────┐
│           LAYER 3: PERSISTENCE & CORE LAYER            │
│     (`src/core (layer # 3)/`: SQLite3 [WAL], TinyDB,   │
│      dtos/, repositories/)                             │
└────────────────────────────────────────────────────────┘

```

### Layer Rules & Boundaries:

- **Layer 1 (Application / Presentation):** Located in `src/app (layer # 1)/`. Manages HTTP routing, controllers, authentication endpoints, and server-side rendered UI templates using Bootstrap 5 and jQuery. It translates user input into service calls and hands responses back to the view layer. **Rule:** Contains zero business rules.
- **Layer 2 (Business Logic / Core):** Located in `src/business (layer # 2)/`. Pure, framework-agnostic Python code. Manages the persona state machine, sliding-window event log memory, prompt compilation logic, and LLM provider strategy contracts. **Rule:** **Forbidden** from importing Flask, FastAPI, SQLAlchemy, or any web/database framework modules. It communicates with storage solely through generic repository interfaces passed via Dependency Injection (DI).
- **Layer 3 (Persistence & Infrastructure):** Located in `src/core (layer # 3)/`. Subdivided into `dtos/` (for database models, view models, and state shapes) and `repositories/` (for data access against SQLite, TinyDB, raw JSON files, and unmanaged resources). **Rule:** Existing repositories must be preserved and reused; new repositories must match the established architectural style.

---

## 3. Core Subsystems & Component Data Flow

### A. Persona & Prompt Engine

- **Metadata Store:** Stores name, gender, profile picture reference, bio, and background story via Layer 3 repositories.
- **Prompt Compiler:** Layer 2 dynamically gathers the persona character sheet, environmental context, and the active event-log node window to build structured prompt payloads for execution.

### B. Time-Series Event Log ("Line of Truth") & Sliding Window

- **Long-Term Memory Structure:** Notable agent experiences and activities are recorded as a plain chronological list of time-series nodes, with relevant historical chat messages attached as child records.
- **Explicit Timeline Editing:** Users can add, edit, and delete nodes through ordinary visible CRUD operations. A node deletion is rejected while any messages remain attached.
- **Message Conversation Management:** Each message records its speaker, content, user-editable conversation time, and explicit per-node position. Users can edit, delete, reorder, or move a message to another node.
- **Sliding Window Token Budgeting:** The internal prompt-context window enforces a configurable **fixed max active node size** without changing the visible Line of Truth list.
- **Cache Invalidation:** Every explicit node or message mutation triggers an immediate cache invalidation hook, forcing Layer 2 to recompile prompt context on the next execution cycle.

### C. Multi-Agent Isolation

- Every Line of Truth query is scoped to the selected `Agent` row.
- The dashboard exposes an agent switcher and carries the selected `agent_id` through edit and message operations.
- Cross-agent node/message mutations are rejected by the Layer 2 service.

### D. Provider Agnostic LLM Routing

- Implements the **Strategy Pattern** via an abstract `BaseProvider` interface.
- Concrete implementations wrap **Ollama** (local inference) and **OpenRouter** (cloud routing), allowing seamless plug-and-play of new LLM backends without altering Layer 2 business logic.

---

## 4. Data Storage & Persistence Schema

### Line of Truth Records

- `event_log_nodes` are ordered by their chronological `sequence_index` and are visible as a plain node list. `agent_id` is a foreign key to `agents.id` with cascade deletion when an agent is removed.
- `messages` belong to a node through a foreign key to `event_log_nodes.id` and store `sender`, `content`, a user-editable conversation `timestamp`, and a per-node `position` used for explicit up/down ordering. The sender is restricted to the local user or the selected agent.
- Moving a message changes only its owning node and sequence position; the user can then correct its conversation timestamp manually.
- A node deletion is rejected by both the business service and the concrete event repository while any child message exists.

### SQLite3 Configuration

- **Concurrency Protection:** SQLite connections must explicitly initialize with Write-Ahead Logging enabled to support background asynchronous agent loops writing logs concurrently with user dashboard activity:
```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;

```