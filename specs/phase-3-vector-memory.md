# Phase 3 Specification: Per-Agent Vector Memory with ChromaDB

> ## 🔲 STATUS: NOT STARTED
> **Last updated:** 2026-09-25
> **Exit gate:** `python -m pytest tests/test_phase_3.py` — **PASSING**
> **Next step:** Phase 4 (prompt generation engine).

| Task | Title | Status |
| ---- | ----- | ------ |
| 1 | Per-Agent Data Directory Layout | ⬜ |
| 2 | ChromaDB Integration (Layer 3) | ⬜ |
| 3 | Vectorize Messages & Topic Nodes | ⬜ |
| 4 | Vector Search Service (Layer 2) | ⬜ |
| 5 | Unit & Integration Testing | ⬜ |

## 1. Objective & Scope

**- Core Goal:** Give each agent its own **vector-indexed memory** so that past conversations, topic nodes, and experiences can be semantically searched. This enables the prompt generation engine (Phase 4) to retrieve relevant memories when constructing the final prompt.

**- In-Scope Deliverables:**
  - **Per-agent data directory:** `data/agents/{agent_id}/` containing:
    - `memory.db` — lightweight SQLite for vector metadata (chunk IDs, source message/node IDs, timestamps, etc.)
    - `chroma/` — ChromaDB vector store directory (persistent, local).
  - **Layer 3 `VectorRepository`:** wraps ChromaDB, supports:
    - `add_vectors_async(items: list[VectorChunk])` — upsert vectors with metadata.
    - `search_async(query: str, top_k: int, agent_id: str) -> list[VectorChunk]` — semantic search scoped to one agent.
    - `delete_vectors_by_source_async(source_type: str, source_id: str, agent_id: str)` — remove vectors when a message/node is deleted.
  - **Layer 2 `VectorizationService`:** text → embedding conversion.
    - Initial embedding source: **sentence-transformers** (local, offline-capable) or a simple API-based embedder.
    - Chunking strategy: one vector per message, plus one vector per topic node summary.
  - **Layer 2 `MemoryVectorService`:** orchestrates vectorization + storage:
    - `index_message_async(message: Message, agent_id: str)` — vectorize and store.
    - `index_node_async(node: EventLogNode, agent_id: str)` — vectorize node summary.
    - `search_memories_async(query: str, agent_id: str, top_k: int) -> list[VectorChunk]`.
    - `on_message_deleted_async(message_id, agent_id)` — remove vectors.
    - `on_node_deleted_async(node_id, agent_id)` — remove vectors.
  - **Integration with EventLogManager:** after appending a message, call `MemoryVectorService.index_message_async()`.
  - **Integration with TopicDetectionService:** after auto-creating a topic node, call `MemoryVectorService.index_node_async()`.

**- Out-of-Scope:** Prompt generation (Phase 4), dashboard UI for vector search (dev-only feature), auth, Termux, marketplace.

---

## 2. Technical Guardrails

- **DO:** Keep Layer 2 framework-independent; `MemoryVectorService` communicates with ChromaDB through a repository interface.
- **DO:** All vector operations are scoped to one agent — no cross-agent vector leakage.
- **DO:** Vector deletion is synchronous with message/node deletion (event-driven or called inline).
- **DON'T:** Store vectors in the main `agent.db` SQLite — use per-agent ChromaDB.
- **DON'T:** Make vector search a user-facing dashboard feature in this phase — it's a backend capability for the prompt engine.
- **DON'T:** Block the main thread on embedding generation; use async or thread-pooled execution.

---

## 3. Implementation Tasks & Checklist

### Task 1: Per-Agent Data Directory Layout — ⬜
- [ ] Define base data path: `AGENT_DATA_DIR` env var, default `src/`.
- [ ] Create `data/agents/{agent_id}/` on first use (when agent is created or when first vector operation occurs).
- [ ] Directory contains:
  - `memory.db` — SQLite for vector metadata (chunk ID, source message/node ID, source type, timestamp, agent_id).
  - `chroma/` — ChromaDB persistent client directory.
- [ ] Update `container.py` to support per-agent vector repositories.

### Task 2: ChromaDB Integration (Layer 3) — ⬜
- [ ] Add `chromadb>=0.4` to `src/requirements`.
- [ ] Create `core/repositories/vector_repository.py` with `ChromaVectorRepository`:
  - Constructor takes `agent_id` and chroma persist directory path.
  - `collection_name = f"agent_{agent_id}"` (or similar scoping).
  - Methods: `add_async()`, `query_async()`, `delete_async()`.
- [ ] Add `memory.db` SQLite schema:
  ```sql
  CREATE TABLE IF NOT EXISTS vector_chunks (
      id TEXT PRIMARY KEY,
      agent_id TEXT NOT NULL,
      source_type TEXT NOT NULL,  -- 'message' or 'node'
      source_id TEXT NOT NULL,    -- message.id or node.id
      content TEXT NOT NULL,      -- original text (for reference)
      metadata_json TEXT,         -- optional extra metadata
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  ```
- [ ] `VectorMetadataRepository` (SQLite) for chunk metadata tracking.

### Task 3: Vectorize Messages & Topic Nodes — ⬜
- [ ] Create `business/memory/vectorization_service.py` with `VectorizationService`:
  - `vectorize_text_async(text: str) -> list[float]` — returns embedding.
  - Initial implementation: use `sentence-transformers` (`all-MiniLM-L6-v2` or similar) via thread pool.
  - Alternative: API-based embedder (OpenRouter, OpenAI) — pluggable via `IEmbeddingProvider` interface.
- [ ] `MemoryVectorService` (Layer 2):
  - `index_message_async(message: Message, agent_id: str)`:
    - Vectorize `message.content`.
    - Store in ChromaDB with metadata: `source_type='message'`, `source_id=message.id`, `sender=message.sender`, `timestamp=message.timestamp`.
    - Insert metadata row into `memory.db`.
  - `index_node_async(node: EventLogNode, agent_id: str)`:
    - Vectorize `node.summary`.
    - Store in ChromaDB with metadata: `source_type='node'`, `source_id=node.id`, `timestamp=node.timestamp`.
    - Insert metadata row.
  - Called automatically by `EventLogManager` after message/node creation.

### Task 4: Vector Search Service (Layer 2) — ⬜
- [ ] `MemoryVectorService.search_memories_async(query: str, agent_id: str, top_k: int = 5) -> list[VectorChunkResult]`:
  - Vectorize the query.
  - Query ChromaDB for similar vectors (scoped to agent's collection).
  - Return results with: `chunk_id`, `source_type`, `source_id`, `content`, `similarity`, `metadata`.
- [ ] `MemoryVectorService.get_relevant_memories_async(agent_id: str, context: str, top_k: int) -> list[VectorChunkResult]`:
  - Higher-level method: given a conversation context, search for relevant memories.
  - Used by Phase 4 prompt engine.
- [ ] Deletion handling:
  - `on_message_deleted_async(message_id, agent_id)` — delete vector by source_id.
  - `on_node_deleted_async(node_id, agent_id)` — delete vectors by source_id.

### Task 5: Unit & Integration Testing — ⬜
- [ ] `tests/test_phase_3.py`:
  - Test vector indexing of a message.
  - Test vector search returns relevant results.
  - Test deletion removes vectors.
  - Test per-agent isolation (search for agent A doesn't return agent B's vectors).
  - Mock embedding function for fast tests.

---

## 4. Exit Gate / Acceptance Test

```bash
python -m pytest tests/test_phase_3.py
```

**Acceptance criteria:**
- Each agent gets its own ChromaDB collection.
- Messages and nodes are vectorized on creation.
- `search_memories_async("coffee recipe")` returns relevant message/node vectors for the selected agent.
- Deleting a message removes its vector.
- Agent A's search doesn't return agent B's memories.
- Works offline with sentence-transformers (no API required).
