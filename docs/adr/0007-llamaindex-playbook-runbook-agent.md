# ADR-0007: LlamaIndex ReActAgent for Playbook and Runbook Retrieval

**Status:** Accepted  
**Date:** 2026-08-24  
**Author:** SRE AI Team

---

## Context

The existing specialist pipeline (metrics, traces, kubernetes, troubleshoot) is optimised for
**telemetry interrogation** — it runs a bounded MCP tool loop and extracts structured Pydantic
findings. Playbook and runbook lookup is a different problem class: it requires **semantic
retrieval over a knowledge corpus** (Confluence pages, GitHub wiki runbooks, structured YAML
playbooks) followed by **reasoning over the retrieved content** to select applicable steps.

Forcing runbook retrieval into the two-phase MCP tool loop would require encoding every
playbook as a Prometheus/Kubernetes/Traces query, which is semantically wrong and prevents
future upgrade to a real vector-store-backed RAG corpus.

Two alternatives were evaluated:

| Approach | Pro | Con |
|---|---|---|
| Encode playbooks as MCP tools (one tool per playbook) | No new dependency | Scales poorly; tool list explodes; no semantic search |
| LlamaIndex ReActAgent + FunctionTools over playbook KB | Semantic search; clean separation; RAG-upgradeable | New dependency (`llama-index-core`) |

---

## Decision

Introduce a **`PlaybookRunbookAgent`** implemented with `llama_index.core.agent.ReActAgent`
wrapping three `FunctionTool`s:

| Tool | Responsibility |
|---|---|
| `search_playbooks(query)` | Keyword/semantic search over playbook KB; returns ranked IDs |
| `get_playbook_steps(playbook_id)` | Retrieve ordered remediation steps for a playbook |
| `get_escalation_path(category)` | Return on-call contacts when no playbook matches |

The agent is exposed as a `PlaybookSpecialist` (extends `BaseSpecialist`) registered under
the canonical domain key `"playbook"` with aliases `runbook`, `remediation`, `sre-runbook`.

`PlaybookSpecialist.execute()` bypasses the inherited two-phase MCP tool loop entirely and
delegates directly to `PlaybookRunbookAgent.execute()` which `await`s the LlamaIndex
`WorkflowHandler` with a 60-second timeout and a deterministic keyword-match fallback.

### LLM Provider Resolution

The agent resolves the best available LLM at runtime via `_build_llama_llm()`:

```
Priority: Anthropic claude-3-5-haiku → OpenAI gpt-4o-mini → Gemini gemini-2.0-flash → MockLLM
```

No new API keys are required; the same `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` /
`GEMINI_API_KEY` environment variables used by the Pydantic-AI layer are reused.

### Corpus (Phase 1)

Phase 1 ships a **hardcoded in-process corpus** of five canonical SRE playbooks
(`PB-001` through `PB-005`) covering OOMKill, high latency, DB connection pool exhaustion,
node pressure, and deployment rollback. The knowledge base is defined in
`src/shepherd/agents/playbook_runbook.py` as `_PLAYBOOKS`.

### Corpus (Phase 2 — future)

The `search_playbooks` tool is intentionally thin: its signature is stable and its
implementation can be swapped for a `pgvector` / `Qdrant` / `ChromaDB` semantic similarity
search without any change to the agent, specialist, or schema.

```python
# Phase 2 drop-in: replace keyword score with embedding similarity
def search_playbooks(query: str) -> str:
    embeddings = embed(query)
    results = vector_store.query(embeddings, top_k=3)
    return format_results(results)
```

---

## Consequences

### Positive

- Playbook retrieval is semantically decoupled from telemetry queries.
- `PlaybookFindings` schema (`matched_playbooks`, `recommended_runbook`, `escalation_path`,
  `RunbookStep`) is strongly typed and flows into `FinalReport.immediate_recommendations`.
- LlamaIndex dependency is additive and isolated to `playbook_runbook.py`; removal requires
  deleting one file and one registry entry.
- Timeout + keyword-match fallback guarantees the pipeline never blocks on LLM availability.

### Negative / Trade-offs

- `llama-index-core` adds ~15 MB to the container image and three additional LLM adapter
  packages (`llama-index-llms-{anthropic,openai,gemini}`).
- `ReActAgent` uses a `workflows.WorkflowHandler` async pattern distinct from Pydantic-AI's
  `Agent.run()` — two async agent execution models now coexist. This is an accepted trade-off
  because the two domains (structured extraction vs. retrieval-augmented reasoning) are
  sufficiently different to justify separate tools.
- Pyright cannot resolve llama-index type stubs (`py.typed` absent); imports carry
  `# type: ignore[import-untyped]` suppression.

---

## Files Changed

| File | Change |
|---|---|
| `pyproject.toml` | Added `llama-index-core`, `llama-index-llms-{anthropic,openai,gemini}` |
| `src/shepherd/agents/playbook_runbook.py` | **New** — LlamaIndex ReActAgent + FunctionTools + keyword corpus |
| `src/shepherd/agents/specialists/playbook.py` | **New** — `PlaybookSpecialist` adapter |
| `src/shepherd/agents/specialists/registry.py` | Registered `PlaybookSpecialist`; added runbook/remediation aliases |
| `src/shepherd/domain/schemas.py` | Added `RunbookStep`, `PlaybookMatch`, `PlaybookFindings` |
| `docs/architecture/high-level-architecture.md` | Added Playbook MCP layer + specialist node |
| `docs/architecture/low-level-architecture.md` | Added `PlaybookFindings` schema + LlamaIndex execution flow |
