# Phase 5 Specification: Plugin System & Marketplace Foundation

## 1. Objective & Scope
- **Core Goal:** Build the dynamic skill plugin loader for runtime extensibility and establish the unified OAuth identity mapping framework bridging the local agent dashboard to the future centralized skill marketplace portal.
- **In-Scope Deliverables:**
  - Dynamic Python module loader that scans a local `plugins/` directory, validates skill signatures, and registers custom code into Layer 2 at runtime.
  - Initial first-party sample skill (e.g., a lightweight prompt optimization or text-compression utility module).
  - Unified OAuth identity linking architecture ensuring the agent dashboard shares the exact same user identity structure as the upcoming marketplace portal.
  - Marketplace-ready API hook structure for third-party developers to publish models, prompt compression packages, or persona experts (e.g., Facebook marketing guides, specialized gaming add-ons).
- **Out-of-Scope:** Building the external commercial e-commerce marketplace backend (leaving doors open for future cloud expansion while keeping local deployment independent).

---

## 2. Technical Guardrails (Do's and Don'ts)
- **DO:** Sandbox dynamically loaded skill modules so they communicate strictly through established Layer 2 service interfaces and cannot bypass security permissions or corrupt core database repositories directly.
- **DO:** Ensure that local agent runtimes can operate 100% offline even if the marketplace portal connection is unavailable.
- **DON'T:** Hardcode third-party plugins into the core framework. All plugins must be dynamically discoverable via directory scanning and configuration flags.

---

## 3. Implementation Tasks & Checklist

- [ ] **Task 1: Dynamic Plugin Loader Engine (Layer 2 & Core)**
  - [ ] Implement `PluginManager` utility to scan local directories (`src/plugins/`), load Python modules dynamically using `importlib`, and validate base skill contracts.
  - [ ] Define standard abstract interface for custom agent skills (inputs, hooks, and execution triggers).

- [ ] **Task 2: First-Party Sample Skill (Extensions)**
  - [ ] Develop a built-in text-compression or prompt-optimization sample skill to validate runtime registration and execution.

- [ ] **Task 3: Unified OAuth Identity Bridge (Layer 1)**
  - [ ] Configure account linking schema so the dashboard session token can authenticate against future marketplace endpoints seamlessly using the same OAuth profile.

- [ ] **Task 4: Integration Testing & Verification**
  - [ ] Write integration test (`tests/test_phase_5.py`) dropping a mock skill into the plugin directory at runtime and confirming the agent discovers and executes it successfully.

---

## 4. Exit Gate / Acceptance Test
To declare **Phase 5 Complete** (and finalize your full feature roadmap), run the test suite:
```bash
python -m pytest tests/test_phase_5.py