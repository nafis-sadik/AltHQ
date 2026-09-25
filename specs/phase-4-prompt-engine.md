# Phase 4 Specification: Prompt Generation Engine (Dev-Only)

> ## 🔲 STATUS: NOT STARTED
> **Last updated:** 2026-09-25
> **Exit gate:** `python -m pytest tests/test_phase_4.py` — **PASSING**
> **Next step:** Phase 5 (dashboard, auth, LLM providers).

| Task | Title | Status |
| ---- | ----- | ------ |
| 1 | PromptGenerationService — Architecture & Interface | ⬜ |
| 2 | Persona Segment Compilation | ⬜ |
| 3 | Vector Memory Retrieval Segment | ⬜ |
| 4 | Recent Messages Segment (last N) | ⬜ |
| 5 | Final Prompt Assembly | ⬜ |
| 6 | Dev-Only Exposure & Testing | ⬜ |

## 1. Objective & Scope

**- Core Goal:** Build a **deep-app prompt generation engine** that constructs the final LLM prompt from three components:
1. **Agent persona** (name, bio, background story, character sheet, persona config).
2. **Vector search results** — relevant memories retrieved from the agent's ChromaDB (Phase 3).
3. **Last N messages** from the Line of Truth (N comes from the agent's `active_node_limit` config).

This engine lives **deep in the application (Layer 2)** and is **NOT exposed on the agent dashboard page**. It is a service for developers/internal use — called by the LLM provider pipeline (Phase 5) when preparing a prompt for the model.

**- In-Scope Deliverables:**
  - `business/prompt/PromptGenerationService` — pure Python, framework-independent.
  - Interface:
    ```python
    class IPromptGenerationService(Protocol):
        async def generate_prompt_async(
            self,
            agent_id: str,
            current_input: str,          # user's latest message
            context: str | None = None,  # optional extra context
        ) -> PromptResult:
            ...
    ```
  - `PromptResult`:
    ```python
    @dataclass
    class PromptResult:
        full_prompt: str           # final prompt string for the LLM
        persona_segment: str       # part 1: persona
        memory_segment: str       # part 2: vector search results
        recent_messages_segment: str  # part 3: last N messages
        metadata: dict             # chunks used, token estimates, etc.
    ```
  - **Segment 1 — Persona:** compiled from `Agent` entity (name, bio, background story, character sheet reference, personality traits). Reuses `PersonaService.CompilePromptSegments()` but extends it.
  - **Segment 2 — Vector Memory:** calls `MemoryVectorService.search_memories_async()` with a query derived from `current_input` + recent context. Formats top K results as a "Relevant Memories" section.
  - **Segment 3 — Recent Messages:** fetches last N messages from `EventLogManager` (N = agent's `active_node_limit`). Formats as a conversation history section.
  - **Assembly:** combines segments in a fixed template:
    ```
    # Persona
    {persona_segment}

    # Relevant Memories
    {memory_segment}

    # Recent Conversation
    {recent_messages_segment}

    # Current Input
    {current_input}

    # Response
    ```
  - **Token budget awareness:** estimates token count of assembled prompt; warns if exceeds model context limit.

**- Out-of-Scope:** Dashboard UI for prompt preview (dev-only), LLM provider API calls (Phase 5), auth, Termux, marketplace.

---

## 2. Technical Guardrails

- **DO:** Keep `PromptGenerationService` in Layer 2 — framework-independent, no Django/Flask imports.
- **DO:** Depend on `IPersonaService`, `IEventLogService`, `IMemoryVectorService` via DI — all injected at composition root.
- **DO:** Make the prompt template configurable (stored in `config.json` or a template file) so developers can tweak without code changes.
- **DON'T:** Expose prompt generation on the agent dashboard page — this is a backend/developer capability.
- **DON'T:** Hard-code the template structure; use a configurable template.
- **DON'T:** Block on vector search for too long — set a timeout on ChromaDB queries.

---

## 3. Implementation Tasks & Checklist

### Task 1: PromptGenerationService — Architecture & Interface — ⬜
- [ ] Create `business/prompt/` directory with `__init__.py` and `prompt_generation_service.py`.
- [ ] Define `IPromptGenerationService` (Protocol) and `PromptResult` dataclass.
- [ ] Define `PromptTemplate` dataclass (template parts, order, separators).
- [ ] `PromptGenerationService` constructor:
  ```python
  def __init__(
      self,
      persona_service: IPersonaService,
      event_log_service: IEventLogService,
      memory_vector_service: IMemoryVectorService,  # from Phase 3
      config: IRuntimeConfig,
  ):
  ```
- [ ] Add `IMemoryVectorService` protocol to `business/prompt/` or reuse from Phase 3.

### Task 2: Persona Segment Compilation — ⬜
- [ ] Extend `PersonaService.CompilePromptSegments()` or create `CompileFullPersonaAsync(agent_id)`:
  - Identity: "You are {name}, a {gender} persona."
  - Bio: "{bio}"
  - Background story: "{background_story}"
  - Character sheet reference: if sheet exists, "Refer to your character reference sheet for visual/physical traits."
  - Personality traits: derive from bio/background if not explicit.
- [ ] Return as `PromptSegment(persona=...)`.

### Task 3: Vector Memory Retrieval Segment — ⬜
- [ ] `PromptGenerationService` calls `memory_vector_service.search_memories_async()`:
  - Build search query from `current_input` + recent message context (last 3 messages).
  - `top_k = 5` (configurable).
- [ ] Format results:
  ```
  ## Relevant Memories
  - [{source_type}] {content} (similarity: {score})
  - ...
  ```
- [ ] If no relevant memories, output "No relevant memories found."

### Task 4: Recent Messages Segment (last N) — ⬜
- [ ] Fetch last N messages from `EventLogManager`:
  - N = agent's `active_node_limit` (from `Agent.active_node_limit`).
  - Get messages from most recent nodes, ordered by position.
- [ ] Format as conversation:
  ```
  ## Recent Conversation
  User: {message_content}
  {Agent name}: {message_content}
  ...
  ```
- [ ] If fewer than N messages exist, include all.

### Task 5: Final Prompt Assembly — ⬜
- [ ] Define default template in `config.json`:
  ```json
  {
    "prompt_template": {
      "persona_section": "# Persona\n{persona}\n",
      "memory_section": "# Relevant Memories\n{memories}\n",
      "conversation_section": "# Recent Conversation\n{messages}\n",
      "input_section": "# Current Input\n{input}\n",
      "response_section": "# Response\n"
    }
  }
  ```
- [ ] `generate_prompt_async()` assembles:
  1. Fetch agent (active or specified).
  2. Compile persona segment.
  3. Search vector memory, format memory segment.
  4. Fetch last N messages, format conversation segment.
  5. Combine with template.
  6. Return `PromptResult`.
- [ ] Token estimation: rough estimate (tokens ≈ chars / 4) and include in metadata.

### Task 6: Dev-Only Exposure & Testing — ⬜
- [ ] **No dashboard route** for prompt preview in this phase.
- [ ] **Dev-only access:** add a debug/admin route or CLI command for developers to test prompt generation:
  - `python -m business.prompt.cli generate --agent-id <id> --input "test message"`
  - Or a dev-only Django route `GET /dev/prompt-preview/?agent_id=<id>&input=<text>` (protected by dev mode check).
- [ ] `tests/test_phase_4.py`:
  - Test persona segment contains agent name, bio.
  - Test memory segment returns vector results (mock vector service).
  - Test conversation segment returns last N messages.
  - Test full prompt assembles correctly.
  - Test token estimation.

---

## 4. Exit Gate / Acceptance Test

```bash
python -m pytest tests/test_phase_4.py
```

**Acceptance criteria:**
- `generate_prompt_async()` returns a `PromptResult` with all three segments.
- Persona segment contains agent identity, bio, background story.
- Memory segment contains relevant vector search results (or "no memories" message).
- Conversation segment contains last N messages (N from agent config).
- Full prompt follows the configurable template.
- Dev-only access works (CLI or debug route).
- No dashboard UI exposed for this feature.
