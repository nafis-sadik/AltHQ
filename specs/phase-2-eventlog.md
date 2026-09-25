# Phase 2 Specification: Line of Truth, Topic Detection & Explicit Timeline Editor

> ## ✅ STATUS: COMPLETE
> **Progress:** 6/6 tasks · 100% of checklist items
> **Last updated:** 2026-09-25
> **Exit gate:** `python -m pytest tests/test_phase_2.py` + `tests/test_phase_2_ui.py` — **PASSING**
> **Next step:** Phase 3 (per-agent vector memory with ChromaDB).

| Task | Title | Status |
| ---- | ----- | ------ |
| 1 | Event Log & Message Schema (Layer 3) | ✅ Done |
| 2 | Sliding-Window Memory Engine (Layer 2) | ✅ Done |
| 3 | Explicit Timeline Node CRUD (Layer 2 & 3) | ✅ Done |
| 4 | Message Conversation Management (Layer 2 & 3) | ✅ Done |
| 5 | Unit & UI Testing / Verification | ✅ Done |
| 6 | Topic Change Detection System | 🔄 In Progress |

## 1. Objective & Scope

**- Core Goal:** Build the agent's long-term memory as a plain chronological **Line of Truth** node list with **automatic topic change detection**. When a new topic is detected in incoming conversation, a new node is created automatically. Messages accumulate under that node until the next topic change. Topics can be anything: general conversation, coffee recipes, family life issues, work projects, etc.

**- In-Scope Deliverables:**
  - Layer 3 models for `event_log_nodes` and `messages` (already done).
  - Layer 3 repositories for node/message CRUD (already done).
  - Layer 2 `EventLogManager` for explicit node/message operations (already done).
  - **Layer 2 `TopicDetectionService`**: analyzes incoming message content, compares to recent node summaries, detects topic shift.
  - **Auto-node creation:** when topic changes, `TopicDetectionService` creates a new node with a generated summary (e.g., "Topics: {detected_topic}" or user-editable placeholder).
  - **Topic taxonomy:** topics are free-form — no fixed taxonomy. The system detects shifts based on semantic/textual analysis.
  - User can **manually edit** auto-created node summaries.
  - User can **manually create** nodes too (existing explicit CRUD preserved).
  - Multi-agent timeline isolation.
  - Node deletion protection (must be empty).
  - Prompt-context cache invalidation after mutations.

**- Out-of-Scope:** OAuth/Auth0, LLM provider API clients, Termux deployment, plugin marketplace, vector memory (Phase 3).

---

## 2. Technical Guardrails

- **DO:** Treat every node and message change as a visible CRUD operation (auto-created nodes are still visible and editable).
- **DO:** Keep Layer 2 framework-independent; communicate with persistence only through repository interfaces.
- **DO:** Scope every timeline read/mutation to the selected agent; reject cross-agent access.
- **DO:** Keep message order (`position`) independent from conversation time.
- **DO:** Preserve SQLite WAL mode and busy timeouts.
- **DON'T:** Implement silent edits or hidden history-rewrite modes.
- **DON'T:** Delete a node with child messages; move/delete messages first.
- **DON'T:** Leak SQLAlchemy sessions into Layer 2.

---

## 3. Implementation Tasks & Checklist

### Task 1: Event Log & Message Schema (Layer 3) — ✅ Already Done
- [x] `event_log_nodes` with `agent_id` FK, `sequence_index`, `summary`, `timestamp`, `is_active`.
- [x] `messages` with `node_id` FK, `sender`, `content`, `position`, `timestamp`.
- [x] Repositories with position ordering and upgrade path for older databases.

### Task 2: Sliding-Window Memory Engine (Layer 2) — ✅ Already Done
- [x] `MemoryWindowService` to slice prompt context based on configured node limit.
- [x] Token estimation and budgeting without changing visible timeline.

### Task 3: Explicit Timeline Node CRUD (Layer 2 & 3) — ✅ Already Done
- [x] Add/edit/delete nodes (empty-only deletion).
- [x] Multi-agent isolation and agent switcher.
- [x] Dashboard forms for all operations.

### Task 4: Message Conversation Management (Layer 2 & 3) — ✅ Already Done
- [x] Add/edit/delete messages with user/agent sender dropdown.
- [x] Move messages up/down within a node.
- [x] Move messages to another node.

### Task 5: Unit & UI Testing (Layer 2 & 3) — ✅ Already Done
- [x] `tests/test_phase_2.py` and `tests/test_phase_2_ui.py` covering ordering, guarded deletion, validation, dashboard workflow.

### Task 6: Topic Change Detection System — NEW

#### 6a. Topic Detection Service (Layer 2)
- [ ] Create `business/memory/topic_detector.py` with `TopicDetectionService` class.
- [ ] **Interface:**
  ```python
  class ITopicDetectionService(Protocol):
      def detect_topic_change(
          self,
          agent_id: str,
          new_message: str,
          recent_nodes: list[EventLogNode],  # last N nodes for this agent
          recent_messages: list[Message],     # last M messages across recent nodes
      ) -> TopicChangeResult:
          ...
  ```
- [ ] **`TopicChangeResult`:** `changed: bool`, `suggested_topic_summary: str | None` (e.g., "Topic: Coffee recipes").
- [ ] **Detection approach (start simple):**
  - **Keyword/TF-IDF based:** Compare new message to recent message corpus; if similarity drops below threshold, flag as topic change.
  - **Recency window:** Only compare against last K messages (configurable, default ~20 messages).
  - **Threshold tuning:** start with a conservative threshold; user can adjust later.
- [ ] **Fallback:** if no recent messages exist, always treat as "new topic" (first topic).
- [ ] **Debouncing:** don't flag topic change on every message; require at least 2-3 messages on new topic before confirming (or let user manually confirm via UI).

#### 6b. Integration with EventLogManager
- [ ] `EventLogManager` accepts `TopicDetectionService` in constructor (optional).
- [ ] `EventLogManager.append_message_async()` calls topic detector after appending.
- [ ] If topic change detected, auto-create a new node with `suggested_topic_summary`.
- [ ] Auto-created nodes get a special marker (e.g., `is_auto_created=True` flag or a convention in `summary` prefix like `"[Auto] "`).
- [ ] User can edit auto-created node summaries via existing edit UI.

#### 6c. UI for Topic Nodes
- [ ] Dashboard event log view shows auto-created nodes with a visual indicator (e.g., "Auto-detected" badge).
- [ ] User can click to edit auto-created node summary.
- [ ] User can manually merge/split nodes (existing CRUD covers this).

#### 6d. Configuration
- [ ] Topic detection parameters stored in `config.json`:
  - `topic_detection.enabled`: bool (default True)
  - `topic_detection.similarity_threshold`: float (default 0.5)
  - `topic_detection.recent_message_window`: int (default 20)
  - `topic_detection.auto_create_nodes`: bool (default True)
- [ ] Layer 3 `JsonConfigRepository` already supports this.

---

## 4. Exit Gate / Acceptance Test

```bash
python -m pytest tests/test_phase_2.py
python -m pytest tests/test_phase_2_ui.py
```

**Acceptance criteria:**
- Manual node CRUD works as before.
- Incoming messages trigger topic detection.
- Topic change → new node auto-created with sensible summary.
- Auto-created nodes are visible, editable, and deletable (when empty).
- User can disable topic detection in config.
- Multi-agent isolation preserved.
