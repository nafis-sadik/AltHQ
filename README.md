# Autonomous Personal AI Agent

A locally hosted personal AI agent framework for desktop environments (Windows/Linux) and future Termux (Android) deployments. The agent is designed around a persistent event-log memory, persona state, and a server-rendered dashboard rather than a conventional stateless chatbot UI.

## Current status

The project follows the phase specifications in [`specs/`](specs/). The implementation currently has these boundaries:

| Phase | Status | Current scope |
| --- | --- | --- |
| 1 — Persona engine | **Complete** | SQLite/WAL persistence, JSON configuration, persona service, CRUD, and UI flows |
| 2 — Event log | **Complete** | Per-agent chronological node CRUD, guarded deletion, constrained message speakers, message ordering/reassignment, manual timestamps, and the internal sliding memory window |
| 3 — Dashboard and providers | **In progress** | Django dashboard vertical slice, persona/sheet management, and event-log UI are present; OAuth/Auth0, LLM providers, and the full Phase 3 exit gate remain |
| 4 — Termux/device bridge | Not started | Mobile setup and background daemon work |
| 5 — Plugin marketplace | Not started | Dynamic plugin loader and marketplace foundation |

The current web layer is **Django** (even though the high-level project documents describe a broader Layer 1 choice). Django's ORM is intentionally not used for application data; all application persistence goes through the Layer 3 repositories.

## Architecture and coding conventions

The code uses the three-layer clean architecture described in [`ARCHITECTURE.md`](ARCHITECTURE.md) and enforced by [`AGENTS.md`](AGENTS.md):

- `src/app` is the application/presentation layer. It contains the Django project, routes, views, templates, and dependency-injection composition root.
- `src/business` is framework-independent business logic. It must not import Django, Flask, FastAPI, SQLAlchemy, SQLite, or other infrastructure frameworks. Persistence is accessed through injected repository protocols.
- `src/core` is the persistence and infrastructure layer. It contains DTOs, async SQLAlchemy repositories, JSON/file repositories, and the SQLite engine.
- SQLite connections use `PRAGMA journal_mode=WAL;`, `PRAGMA busy_timeout=5000;`, and `PRAGMA foreign_keys=ON;`. Event nodes reference `agents.id` and timelines are isolated per agent.
- Repository interfaces are preferred over framework-specific calls in business code. Existing repositories should be reused and preserved.
- Async repository/service methods use the `_async` suffix where the existing code does so, and public functions/classes include type hints and explanatory docstrings.
- The UI is server-rendered HTML using Bootstrap 5 and jQuery. Do not introduce React, Vue, or Tailwind for this project.

## Requirements

- Python **3.12 or newer** (the current environment uses Python 3.13).
- A modern web browser for the dashboard.
- Internet access on the first dependency installation and for the CDN-hosted Bootstrap/jQuery assets.

The dependency manifest is [`src/requirements`](src/requirements). It includes the runtime packages and `pytest` for the test/debug configurations.

## First-time setup

Run these commands from the repository root. The commands below use the repository's conventional `src/venv` location.

### Windows PowerShell

```powershell
py -3.13 -m venv .\src\venv
.\src\venv\Scripts\python.exe -m pip install --upgrade pip
.\src\venv\Scripts\python.exe -m pip install -r .\src\requirements
```

If Python 3.13 is not installed, use another installed Python 3.12+ version in the first command, for example `py -3.12 -m venv .\src\venv`.

### Linux/macOS

```bash
python3 -m venv src/venv
src/venv/bin/python -m pip install --upgrade pip
src/venv/bin/python -m pip install -r src/requirements
```

The repository already contains a `src/venv` in this development environment, so the installation step can be skipped if it already contains the dependencies.

## Run the dashboard

Start Django from the repository root:

**Windows**

```powershell
.\src\venv\Scripts\python.exe .\src\app\manage.py runserver 127.0.0.1:8000 --noreload
```

**Linux/macOS**

```bash
src/venv/bin/python src/app/manage.py runserver 127.0.0.1:8000 --noreload
```

Then open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in a browser. Omit `--noreload` for normal development auto-reload.

Useful routes:

- `/` — persona dashboard; create a persona at `/persona/new/` when the database is empty.
- `/events/` — selected agent's Line of Truth node list and conversation editor; use the agent switcher or `?agent_id=<id>` to select another agent.
- `/persona/new/` — persona creation form.
- `/agents/` — browse every agent and set the persisted active agent.
- `/avatar/` — current avatar or placeholder image.

Both domains are exposed with RESTful JSON API endpoints (routes are owned by
`PersonaController` and `EventLogController` in `src/app/dashboard/controllers/`;
all business logic is delegated to the injected `IPersonaService` /
`IEventLogService` implementations):

Persona domain:

- `GET` / `POST /api/personas/` — paged persona list / create (create returns `201`).
- `GET` / `PUT /api/personas/<agent_id>/` — persona detail / update (`422` on validation errors).
- `POST /api/agents/<agent_id>/set_active/` — atomically set the active agent.
- `POST /api/avatar/generate/` — request AI profile picture generation (`501` until a provider is plugged in).
- `POST /api/sheets/` — upload a character reference sheet.
- `DELETE /api/sheets/<sheet_id>/` — remove a reference sheet.

Line of Truth domain:

- `POST /api/events/` — create a timeline node.
- `PUT` / `DELETE /api/events/<node_id>/` — edit a node summary / delete an empty node (`409` when it still has messages).
- `POST /api/events/<node_id>/messages/` — append a message to a node.
- `PUT` / `DELETE /api/messages/<message_id>/` — edit or delete a message.
- `PUT /api/messages/<message_id>/move/` — move a message to another node (`node_id`) or reorder it (`direction=up|down`).

`PUT`/`DELETE` requests are sent with jQuery-serialized, urlencoded form bodies;
the Layer 1 controllers parse them for any HTTP verb (Django only populates
`request.POST` for `POST`).

### Line of Truth workflow

The event page is a plain chronological node list rather than a hidden history-rewrite mode:

- Add, edit, and delete timeline nodes through visible controls.
- A node can be deleted only after all messages attached to it have been deleted or moved elsewhere.
- Add a message under any node with its speaker selected from the fixed **User / current AI agent** dropdown, text, and optional conversation time (stored/displayed in UTC). Leaving the time blank uses the current time.
- Edit a message to change its speaker, text, conversation time, or owning node.
- Use the up/down controls to change a message's explicit sequence position. Conversation time remains independently editable so a moved message can be assigned the correct time.
- Switch the active agent from the dashboard selector; use **New agent** to create another Agent persona. The switcher persists the active agent, and `/agents/` provides the same control. Each agent has an independent timeline and the AI option in **Said by** always refers to the currently selected agent.

The application creates its persistence schema on first use. Django migrations are not required for this project because `DATABASES` is empty and the Layer 3 repositories create the SQLite tables directly.

### Local data

By default, the composition root uses `src` as its data directory:

- `src/config.json` — runtime configuration.
- `src/agent.db` — SQLite database (ignored by Git; WAL sidecar files may appear beside it).
- `src/sheets/` — uploaded character reference images.

On startup, the SQLAlchemy repository bootstraps the current `agents` schema with its database-enforced single-active-agent invariant; the feature-focused `AgentRepository` does not manage schema lifecycle or upgrade legacy agent tables. The event repository upgrades older databases with the `event_log_nodes.agent_id` foreign key, and the message repository adds the message `node_id` foreign key and explicit `position` column while backfilling legacy rows by timestamp. Set `AGENT_CONFIG_DIR` to another directory when you want isolated local data. Django settings read `src/.env`; `DJANGO_DEBUG=0` and `DJANGO_SECRET_KEY` can be supplied there for a non-development deployment. Do not commit real secrets.

## Run and debug in Visual Studio Code

The checked-in [`.vscode/`](.vscode/) folder is configured for this repository:

- `settings.json` selects the project interpreter, enables pytest discovery, and adds `src` plus `src/app` to the editor's analysis path.
- `launch.json` provides a Django server debug configuration, pytest debug configurations, and a current-file Python configuration.
- `tasks.json` provides one-click server, test, and dependency-install tasks.
- `extensions.json` recommends the Python, debugpy, Pylance, Python Environments, and Django extensions.

### Run or debug without typing commands

1. Open the **repository root** (`AltHQ`) in VS Code, not only `src/app`.
2. Accept the recommended extensions when prompted. If they are not shown, open **Extensions** and install:
   - Python
   - Python Debugger (debugpy)
   - Pylance
   - Python Environments
   - Django
3. Open the Run and Debug view with `Ctrl+Shift+D` (or `Cmd+Shift+D` on macOS).
4. Select **Django: runserver (debug)** and press `F5`.
5. Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in the browser. Stop the server from VS Code's debug toolbar; no terminal command is required.
6. Set breakpoints in files such as `src/app/dashboard/views.py`, `src/business/persona/persona_service.py`, or `src/core/repositories/agent_repository.py`. The server configuration uses `--noreload`, so breakpoints remain attached to one process.

The Python interpreter setting points to `src/venv/Scripts/python.exe` on Windows. If VS Code reports an invalid interpreter, use **Python: Select Interpreter** and choose the project environment manually. On Linux/macOS, select `src/venv/bin/python` if using the checked-in configuration on a different operating system.

### Run the tests

The Test Explorer can discover the suite through **Python: Configure Tests**. To run or debug it directly:

- Select **Pytest: all tests** in Run and Debug and press `F5`, or
- Use the VS Code Test Explorer and run the discovered tests.

The equivalent command-line check is:

**Windows**

```powershell
.\src\venv\Scripts\python.exe -m pytest -q
```

**Linux/macOS**

```bash
src/venv/bin/python -m pytest -q
```

The Phase 1 and Phase 2 exit-gate files can also be selected from the debug configuration. To run them individually with the project interpreter:

**Windows**

```powershell
.\src\venv\Scripts\python.exe -m pytest tests/test_phase_1.py tests/test_phase_1_ui.py
.\src\venv\Scripts\python.exe -m pytest tests/test_phase_2.py tests/test_phase_2_ui.py
```

**Linux/macOS**

```bash
src/venv/bin/python -m pytest tests/test_phase_1.py tests/test_phase_1_ui.py
src/venv/bin/python -m pytest tests/test_phase_2.py tests/test_phase_2_ui.py
```

### Optional VS Code tasks

Open **Terminal > Run Task** only if you want to use a task instead of the debug buttons:

- **Django: runserver (task)** — starts the same local server.
- **Pytest: all tests** — runs the complete test suite.
- **Install dependencies** — reinstalls packages from `src/requirements`.

The Run and Debug configurations are the recommended path when you do not want to use the integrated terminal.

## Troubleshooting

- **`No module named pytest`**: activate the project environment and reinstall `src/requirements`, then reload the VS Code window.
- **Django cannot be imported**: select `src/venv/Scripts/python.exe` (or `src/venv/bin/python`) as the interpreter.
- **Port 8000 is already in use**: change `127.0.0.1:8000` in `README.md`, `.vscode/launch.json`, or `.vscode/tasks.json` to another port.
- **Bootstrap or jQuery styling/scripts are missing**: the templates load them from public CDNs; allow browser network access to jsDelivr/code.jquery.com.
- **Database/schema errors**: stop the server, remove the local `src/agent.db` and its `*-wal`/`*-shm` sidecars, then restart; the repository bootstrap will recreate the tables.
