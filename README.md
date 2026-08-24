# SRE AI Multi-Agent Investigation Platform

An automated multi-agent root cause analysis (RCA) and troubleshooting system modeled after Trendyol's production SRE AI Agents architecture.

```text
                                 ┌──────────────┐
                                 │ Entry Router │
                                 └──────┬───────┘
                                        │
                                 ┌──────▼───────┐
                                 │ Gather Agent │
                                 └──────┬───────┘
                                        │ (Send Fan-Out)
                  ┌─────────────────────┼─────────────────────┐
                  ▼                     ▼                     ▼
          ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
          │ Metrics Spec  │     │  Traces Spec  │     │   K8s Spec    │
          └───────┬───────┘     └───────┬───────┘     └───────┬───────┘
                  │ (Typed Findings)    │                     │
                  └─────────────────────┼─────────────────────┘
                                        ▼
                              ┌───────────────────┐
                              │  Correlate Agent  │ (Zero Tool Access)
                              └─────────┬─────────┘
                                        │
                              ┌─────────▼─────────┐
                              │  Evaluation Gate  │ (Deterministic Python Rule)
                              └────┬─────────┬────┘
                 (Unvalidated)     │         │ (Cross-Validated / Max Rounds)
                 ┌─────────────────┘         └─────────────────┐
                 ▼                                             ▼
          ┌───────────────┐                           ┌───────────────────┐
          │   Deep Dive   │ ────────(Loop Back)──────>│ Synthesize Agent  │
          └───────────────┘                           └─────────┬─────────┘
                                                                ▼
                                                      ┌───────────────────┐
                                                      │    FinalReport    │
                                                      └─────────┬─────────┘
                                                                │
                                                      ┌─────────▼─────────┐
                                                      │  Post-Inv Chat    │ (Live MCP Access)
                                                      └───────────────────┘
```

---

## Key Architectural Principles

1. **Domain-Scoped MCP Tooling:** Specialists only access tools in their domain (Metrics, Traces, Kubernetes, Troubleshoot) to avoid context bloat and off-target queries.
2. **Composite Tools:** Merges multiple operations into single calls (`diagnose_pod`, `get_service_golden_signals`, `jaeger_search_service_traces`) returning dense Markdown.
3. **Two-Phase Specialist Execution:**
   - **Phase 1:** Guardrailed tool-use loop (duplicate suppression, 50KB/result limit, iteration limit).
   - **Phase 2:** Tool-free structured extraction into typed Pydantic models with `SafeFloat`/`SafeInt` coercion.
4. **Tool-Free Correlate Node:** Operates strictly on structured findings with zero tool access to eliminate hallucinated evidence chains.
5. **Cross-Validation Rule:** Requires independent corroboration by $\ge 2$ specialists for high-confidence root cause attribution.
6. **Deterministic Evaluation Gate:** Python `if/else` logic controls routing with a hard cap of 2 deep dive rounds.
7. **Post-Investigation Chat:** Stateful interactive conversation on top of checkpointed investigation reports with live MCP access.
8. **1-5 Star Continuous Feedback:** Captures user ratings and comments to evaluate prompt and tool efficacy.

---

## Directory Structure

```text
sre-ai/
├── CONTEXT.md                                   # Domain Ubiquitous Language & Glossary
├── docs/
│   ├── adr/                                     # Architecture Decision Records (0001 - 0005)
│   └── architecture/
│       ├── high-level-architecture.md           # System context & data flow diagrams
│       └── low-level-architecture.md            # LangGraph state machine & sequence specs
├── manifests/
│   └── scenario-oom-incident.yaml               # Realistic OOMKilled & CrashLoop incident scenario
├── scripts/
│   ├── setup-kind-e2e.sh                        # Automated Kind cluster & scenario deployment
│   ├── run-e2e-incident.py                      # Multi-agent investigation runner against live cluster
│   └── cleanup-kind.sh                          # Kind cluster teardown script
├── src/
│   └── sre_ai/
│       ├── config/                              # Model profiles & runtime settings
│       ├── domain/                              # Pydantic schemas, findings & safe coercion
│       ├── mcp/                                 # Domain-scoped MCP clients & composite tools
│       ├── agents/                              # Specialist registry, guardrails & pipeline agents
│       ├── graph/                               # LangGraph state, Send() fan-out & Entry Router
│       └── server/                              # FastAPI REST & feedback endpoints
└── tests/                                       # End-to-end integration & unit test suite
```

---

## End-to-End Testing with Local Kind (Kubernetes in Docker)

A real-world incident test scenario (`OOMKilled` & `CrashLoopBackOff` microservice failure) is provided under `manifests/scenario-oom-incident.yaml`.

### 1. Provision Kind Cluster & Deploy Incident Scenario
```bash
./scripts/setup-kind-e2e.sh
```
*This script starts Docker/Colima/OrbStack if needed, creates a `sre-ai-e2e` Kind cluster, and deploys a memory-constrained `order-api` deployment in namespace `ecommerce-demo`.*

### 2. Run Autonomous Incident Investigation & Post-Investigation Chat
```bash
python scripts/run-e2e-incident.py
```
*The multi-agent system inspects the live cluster, diagnoses pod exit code 137 (`OOMKilled`), correlates with metrics and traces, outputs the RCA report, and opens an interactive chat turn.*

### 3. Cleanup Test Cluster
```bash
./scripts/cleanup-kind.sh
```

---

## CI/CD Automation (GitHub Actions)

- **CI Pipeline (`.github/workflows/ci.yml`)**:
  - Runs linting and unit/integration test matrix on Python 3.11 & 3.12.
  - Builds and validates the production Docker container image.
- **E2E Kind Pipeline (`.github/workflows/e2e.yml`)**:
  - Spawns a real ephemeral Kubernetes Kind cluster on the GitHub runner.
  - Deploys the `OOMKilled` microservice failure scenario.
  - Executes the multi-agent investigation pipeline against the live cluster to verify real-world RCA and post-investigation chat.

---

## Running the Service & Tests

### Run Tests
```bash
PYTHONPATH=src pytest tests/ -v
```

### Run FastAPI Server
```bash
uvicorn sre_ai.server.app:app --host 0.0.0.0 --port 8000 --reload
```
