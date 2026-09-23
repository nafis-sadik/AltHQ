# Phase 4 Specification: Android/Termux Runtime & Device Bridge

## 1. Objective & Scope
- **Core Goal:** Package the application for seamless local execution on desktop environments (`venv` on Windows/Linux) and natively on mobile hardware via **Termux on Android**, implementing background daemonization and device integration hooks.
- **In-Scope Deliverables:**
  - Automated setup script for Termux environments (handling Python dependencies, storage permissions, and SQLite file path mapping).
  - Background daemon script utilizing `termux-wake-lock` and a persistent process manager (e.g., `screen` or lightweight shell service) to prevent Android from killing the application loop when the phone screen locks.
  - Desktop startup script for Windows and Linux (`venv` activation and server boot).
  - Device communication bridge hooks to ingest context from local messaging and app channels (such as Telegram, WhatsApp, and email notifications).
- **Out-of-Scope:** The plugin loader and skill marketplace backend (reserved for Phase 5).

---

## 2. Technical Guardrails (Do's and Don'ts)
- **DO:** Ensure all mobile-specific environment hooks (like Termux storage permissions or wake locks) are isolated inside setup and startup scripts, keeping core application layers cross-platform.
- **DO:** Configure SQLite paths conditionally based on the execution environment (e.g., pointing to internal Termux application directories on Android vs. local project folders on desktop).
- **DON'T:** Let mobile battery management terminate the agent loop silently without wake-lock protections.

---

## 3. Implementation Tasks & Checklist

- [ ] **Task 1: Cross-Platform Environment & Path Handlers (Layer 3)**
  - [ ] Implement environment detection to configure database storage paths for desktop (`venv`) vs Android (`Termux` home storage).
  - [ ] Write initialization scripts for dependency resolution (`pip install -r requirements.txt`).

- [ ] **Task 2: Termux Setup Script & Storage Setup (Mobile)**
  - [ ] Create `scripts/setup_termux.sh` to request storage permissions (`termux-setup-storage`) and install necessary build dependencies.

- [ ] **Task 3: Background Daemon & Wake-Lock Wrapper (Mobile)**
  - [ ] Implement `scripts/run_daemon.sh` incorporating `termux-wake-lock` and persistent process execution to prevent background termination.

- [ ] **Task 4: Desktop Startup Script (Desktop)**
  - [ ] Create simple batch/bash scripts for Windows and Linux to spin up the application stack inside local virtual environments.

- [ ] **Task 5: Integration Testing & Field Verification**
  - [ ] Test the startup and background persistence cycle locally on desktop and inside a Termux emulator environment.

---

## 4. Exit Gate / Acceptance Test
To declare **Phase 4 Complete**, execute the environment verification check:
```bash
bash scripts/verify_runtime.sh