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

- **Long-Term Memory Structure:** Notable agent experiences and activities are recorded as time-series nodes in an event graph, with relevant historical chat messages attached as child nodes.
- **Sliding Window Token Budgeting:** Enforces a configurable **fixed max active node size** to manage token constraints.
- **God-Mode Stealth Editor:** Users can update past nodes and messages directly via the dashboard. Layer 3 writes these updates *without* generating audit logs or system edit markers, ensuring the agent accepts edited historical realities as absolute truth.
- **Cache Invalidation:** Any stealth edit triggers an immediate cache invalidation hook, forcing Layer 2 to recompile the active prompt window on the next execution cycle.

### C. Provider Agnostic LLM Routing

- Implements the **Strategy Pattern** via an abstract `BaseProvider` interface.
- Concrete implementations wrap **Ollama** (local inference) and **OpenRouter** (cloud routing), allowing seamless plug-and-play of new LLM backends without altering Layer 2 business logic.

---

## 4. Data Storage & Persistence Schema

### SQLite3 Configuration

- **Concurrency Protection:** SQLite connections must explicitly initialize with Write-Ahead Logging enabled to support background asynchronous agent loops writing logs concurrently with user dashboard activity:
```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;

```