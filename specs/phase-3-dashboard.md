# Phase 5 Specification: Dashboard, Auth & Model Provider Integration

## 1. Objective & Scope
- **Core Goal:** Wrap the core engine (Layers 2 & 3) in a web framework (Flask/FastAPI), build the server-side rendered Bootstrap 5 + jQuery dashboard, integrate Auth0/OAuth authentication, implement the explicit Line of Truth history editor UI, and establish LLM provider connectivity (Ollama & OpenRouter).
- **In-Scope Deliverables:**
  - Layer 1 application setup (Flask or FastAPI) with MVC blueprint structure.
  - 3rd-party OAuth/Auth0 integration handling secure login, session management, 2FA, and password recovery.
  - Server-side rendered Bootstrap 5 views with jQuery async triggers for managing persona settings (name, bio, background story, and prompt window size slider).
  - Explicit history editor interface allowing users to view and edit event log nodes and messages, including message order and node reassignment.
  - Provider Strategy Pattern implementation (`BaseProvider` -> `OllamaProvider` and `OpenRouterProvider`) for model execution via user API tokens.
- **Out-of-Scope:** Termux background daemonization, OS app hooks (Telegram/WhatsApp), and the plugin marketplace backend.

---

## 2. Technical Guardrails (Do's and Don'ts)
- **DO:** Ensure all route handlers in Layer 1 act strictly as thin controllers—delegating all business logic to Layer 2 services.
- **DO:** Use server-side rendered HTML templates styled with Bootstrap 5 and jQuery for asynchronous form submissions. Avoid heavy frontend frameworks like React or Vue.
- **DON'T:** Import database sessions or SQLAlchemy models directly inside web view controllers. Access data strictly through Layer 3 repositories or Layer 2 service facades.

---

## 3. Implementation Tasks & Checklist

- [ ] **Task 1: Web Framework & MVC Setup (Layer 1)**
  - [ ] Initialize Flask/FastAPI application structure with clean blueprint routing (`/auth`, `/dashboard`, `/agent`, `/api`).
  - [ ] Configure static asset delivery and server-side Jinja2 template rendering.

- [ ] **Task 2: OAuth & Auth0 Integration (Layer 1)**
  - [ ] Implement secure login, logout, password recovery, and 2FA flows via Auth0/OAuth.
  - [ ] Protect dashboard routes with session authentication middleware.

- [ ] **Task 3: Bootstrap 5 & jQuery Agent Dashboard (Layer 1)**
  - [ ] Build the main dashboard view for switching between multiple Agent personas and editing the selected persona configuration (name, gender, bio, background story).
  - [ ] Implement the prompt sliding window sizing slider with AJAX/jQuery background updates.
  - [ ] Build the interactive Line of Truth viewer for the selected Agent with explicit node and message CRUD, fixed User/Agent speaker selection, ordering, and reassignment controls.

- [ ] **Task 4: LLM Provider Strategy Implementation (Layer 2)**
  - [ ] Define abstract `BaseProvider` interface with an execution method.
  - [ ] Implement `OllamaProvider` for local inference connection.
  - [ ] Implement `OpenRouterProvider` for cloud routing with token authorization headers.

- [ ] **Task 5: Unit & Integration Testing**
  - [ ] Write integration tests (`tests/test_phase_5.py`) verifying dashboard route access control, persona updates via UI forms, and mock LLM provider execution.

---

## 4. Exit Gate / Acceptance Test
To declare **Phase 5 Complete**, run the validation test suite:
```bash
python -m pytest tests/test_phase_5.py