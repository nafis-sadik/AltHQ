# Autonomous Personal AI Agent

An open-source, locally-hosted personal AI agent framework designed to run natively on mobile hardware via **Termux (Android)** as well as desktop environments (**Windows/Linux**).

Unlike traditional chatbot web apps, this agent is built to integrate deeply with your device environment, operating background loops, managing a time-series event log "truth" engine, and maintaining long-term humanoid behavior.

---

## 🏗️ Core Architecture (3-Layer Pattern)

The codebase strictly separates concerns to ensure maintainability and framework independence:

1. **Layer 1 (Application & Presentation):** Flask/FastAPI backend with server-side rendered **Bootstrap 5 & jQuery** dashboard, Auth0/OAuth authentication, and controller routing.
2. **Layer 2 (Business Logic & Engine):** Pure, framework-agnostic Python core managing the persona state machine, prompt compilation, sliding-window event log memory, and LLM provider strategy pattern.
3. **Layer 3 (Persistence & Infrastructure):** Generic repository pattern wrapping SQLAlchemy for **SQLite3 (WAL mode)**, raw JSON configurations, and vector DB layers.

---

## 🚀 Tech Stack

- **Language:** Python 3.11+
- **Backend Framework:** Flask or FastAPI (Layer 1)
- **Frontend:** Bootstrap 5, jQuery, Server-Side Rendered HTML
- **Persistence:** SQLite3 (WAL mode), SQLAlchemy, Raw JSON files
- **Auth:** OAuth / Auth0 / Supabase Auth
- **Inference Providers:** Ollama (Local) & OpenRouter (Cloud)
- **Mobile Runtime:** Termux (Android with background daemon support)

---

## 📂 Project Structure

```text
root/
├── AGENTS.md                       # Universal system guardrails & 3-layer architecture laws
├── ARCHITECTURE.md                 # Big-picture design, data-flow diagrams
├── README.md                       # Project overview for humans
├── specs/                          # Feature-wise Agile sprint specifications
│   ├── phase-1-persona.md          # SRS for Persona Engine
│   ├── phase-2-eventlog.md         # SRS for Time-Series Event Log & God-Mode
│   ├── phase-3-dashboard.md        # SRS for UI, Auth & LLM Providers
│   ├── phase-4-termux.md           # SRS for Android/Termux & Device Bridge
│   └── phase-5-marketplace.md      # SRS for Plugin Loader & Marketplace
├── src/                            # Application source code
│   ├── app (layer # 1)/            # UI, controllers, web routing
│   ├── business (layer # 2)/       # Persona engine, memory windows, prompts
│   └── core (layer # 3)/           # Repositories, DB models, storage
│       ├── dtos                    # DB models & view models
│       └── repositories            # Repositories to access database and other unmanaged resources
└── tests/                          # Unit and integration test suites
```