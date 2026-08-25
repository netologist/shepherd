<div align="center">

# 🐑 Shepherd

### Autonomous SRE AI Multi-Agent Incident Investigation & Root Cause Analysis Platform

[![CI - Build & Test](https://github.com/netologist/shepherd/actions/workflows/ci.yml/badge.svg)](https://github.com/netologist/shepherd/actions/workflows/ci.yml)
[![E2E - Kubernetes Kind](https://github.com/netologist/shepherd/actions/workflows/e2e.yml/badge.svg)](https://github.com/netologist/shepherd/actions/workflows/e2e.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg)](https://www.python.org/downloads/)
[![Architecture](https://img.shields.io/badge/Architecture-LangGraph%20%2B%20Scoped%20MCP-orange.svg)](docs/architecture/high-level-architecture.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*Inspired by and built upon the production architecture documented in [Trendyol Tech: SRE AI Agents in Trendyol](https://medium.com/trendyol-tech/sre-ai-agents-in-trendyol-098057b9dd31).*

</div>

---

## 📖 Table of Contents

1. [Executive Summary & Background](#-executive-summary--background)
2. [Key Production Lessons from Trendyol](#-key-production-lessons-from-trendyol)
3. [Architecture Overview](#-architecture-overview)
4. [Core Architectural Pillars](#-core-architectural-pillars)
   - [1. Domain-Scoped MCP & Composite Tools](#1-domain-scoped-mcp--composite-tools)
   - [2. Two-Phase Specialist Execution](#2-two-phase-specialist-execution)
   - [3. Tool-Free Correlation & Cross-Validation Rule](#3-tool-free-correlation--cross-validation-rule)
   - [4. Deterministic Evaluation Gate & Deep Dive Loop](#4-deterministic-evaluation-gate--deep-dive-loop)
   - [5. Model Profiles & Multi-Tier Fallback Chain](#5-model-profiles--multi-tier-fallback-chain)
   - [6. Production Guardrails & Safe Coercion](#6-production-guardrails--safe-coercion)
   - [7. Stateful Post-Investigation Chat](#7-stateful-post-investigation-chat)
   - [8. Continuous 1-5 Star Feedback Loop](#8-continuous-1-5-star-feedback-loop)
5. [Project Directory Structure](#-project-directory-structure)
6. [Getting Started & Installation](#-getting-started--installation)
7. [Usage Guide](#-usage-guide)
   - [Python API Usage](#python-api-usage)
   - [FastAPI REST Endpoints](#fastapi-rest-endpoints)
   - [Interactive Terminal RCA Runner](#interactive-terminal-rca-runner)
8. [End-to-End Testing with Local Kind Cluster](#-end-to-end-testing-with-local-kind-cluster)
9. [CI/CD Automation (GitHub Actions)](#-cicd-automation-github-actions)
10. [Architecture Decision Records (ADRs)](#-architecture-decision-records-adrs)

---

## 🎯 Executive Summary & Background

In complex, distributed microservice architectures (+20,000 services, +2,000 databases, millions of requests/second), an incident triggers an avalanche of downstream symptoms: database pool starvations, HTTP 504 gateway timeouts, circuit breaker trips, and container memory ballooning.

Asking a single monolithic AI agent to *"find the root cause"* typically backfires—it floods responders with false positives and identifies symptom services rather than the true culprit.

**Shepherd** implements a collaborative multi-agent investigation pipeline that:
- Runs automatically when an incident or P1/P2 alert is declared.
- Fans out domain-isolated specialists (Metrics, Traces, Kubernetes, Troubleshooting) in parallel.
- Enforces an evidence-only cross-validation gate to filter noise.
- Produces a structured `FinalReport` with an actionable evidence chain, timeline, and remediation tasks.
- Transitions into a stateful, tool-enabled assistant allowing SRE on-call engineers to interrogate findings interactively.

---

## 💡 Key Production Lessons from Trendyol

Shepherd codifies the real-world operational insights published in the Trendyol Tech case study:

1. **Avoid Monolithic Toolsets:** Exposing ~200 tools in a single MCP server causes agents to make off-target calls (e.g. Kubernetes agent attempting Jaeger PromQL queries) and burns millions of tokens. Shepherd uses **domain-scoped MCP servers** (~50-60 scoped tools per specialist).
2. **Composite MCP Tools:** Merging 3-4 consecutive tool calls (e.g., `describe pod`, `get events`, `get usage`) into single composite operations like `diagnose_pod` and `application_perf_overview` reduces tool turns and token usage by ~40%.
3. **Tool-Free Correlator:** Giving the correlation node tool access tempts it to hallucinate new investigations. Keeping it tool-free forces it to act strictly as an evidence synthesizer over specialist findings.
4. **Deterministic Control Flow:** LLMs should never decide graph routing loops. Control flow transitions (Deep Dive vs. Synthesis) are governed by deterministic Python rules.
5. **Phase-Specific Model Profiles:** Using expensive models (e.g. Claude Opus) everywhere is slow (~9 mins) and costly. Tiered model allocation (Fast Flash models for Gather/Prefetch, Balanced Pro models for Specialists, Deep-Reasoning models for Correlation/Synthesis) lowers end-to-end run time to ~4 minutes.
6. **Multi-Model & Deterministic Fallback:** An investigation must never fail with an uncaught exception. If all LLMs fail, a deterministic template report is assembled from raw specialist findings.

---

## 🏛 Architecture Overview

```text
                                 ┌──────────────┐
                                 │ Entry Router │
                                 └──────┬───────┘
                                        │
                                 ┌──────▼───────┐
                                 │ Gather Agent │ (Regex Extraction + Parallel Prefetch)
                                 └──────┬───────┘
                                        │ (LangGraph Send Fan-Out)
                  ┌─────────────────────┼─────────────────────┐
                  ▼                     ▼                     ▼
          ┌───────────────┐     ┌───────────────┐     ┌───────────────┐
          │ Metrics Spec  │     │  Traces Spec  │     │   K8s Spec    │
          │ (PromQL/Perf) │     │ (Jaeger/OTel) │     │ (Read-Only)   │
          └───────┬───────┘     └───────┬───────┘     └───────┬───────┘
                  │                     │                     │
                  │ (Typed Pydantic Findings Extraction)      │
                  └─────────────────────┼─────────────────────┘
                                        ▼
                              ┌───────────────────┐
                              │  Correlate Agent  │ (Zero Tool Access / Evidence Matching)
                              └─────────┬─────────┘
                                        │
                              ┌─────────▼─────────┐
                              │  Evaluation Gate  │ (Deterministic Python Rule)
                              └────┬─────────┬────┘
                 (Unvalidated)     │         │ (Cross-Validated / Max Rounds = 2)
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
                                                      │  Post-Inv Chat    │ (Stateful + Live MCPs)
                                                      └───────────────────┘
```

---

## ⚙️ Core Architectural Pillars

### 1. Domain-Scoped MCP & Composite Tools
Specialists interact only with domain-isolated MCP servers:
- **`metrics-mcp`**: PromQL queries, `get_service_golden_signals`, `application_perf_overview`.
- **`traces-mcp`**: Jaeger span waterfalls, `search_jaeger_traces`, `jaeger_search_service_traces`.
- **`k8s-mcp`**: Read-only cluster inspection, `list_pod_status`, `get_pod_events`, `diagnose_pod`, `get_workload_overview`.
- **`troubleshoot-mcp`**: Pre-checks, `investigate_incident`, `get_intelligent_troubleshooting`, `run_static_infra_checks`.

*All MCP tools format responses into concise, structured Markdown tables, eliminating verbose JSON overhead.*

### 2. Two-Phase Specialist Execution
Every specialist executes in two sequential phases:
- **Phase 1 (Tool-Use Loop):** Iterative research against domain MCP tools bounded by iteration caps, per-call size limits (50KB), and duplicate suppression.
- **Phase 2 (Structured Extraction):** Tool-free LLM extraction converting accumulated telemetry notes into strongly-typed Pydantic models (`MetricsFindings`, `TraceFindings`, `KubernetesFindings`).

### 3. Tool-Free Correlation & Cross-Validation Rule
The **Correlate Agent** has zero tool access. It receives typed findings from all specialists and tests for convergence:
$$\text{Primary Root Cause} \iff \text{Corroborated by } \ge 2 \text{ independent specialists}$$
Single-source anomalies remain marked as *contributing factors* rather than root causes.

### 4. Deterministic Evaluation Gate & Deep Dive Loop
Routing after correlation is executed by a pure Python rule:
```python
def route_after_evaluation(correlation, deep_dive_count):
    if deep_dive_count >= 2:
        return "synthesize"
    if correlation and correlation.confidence == "high" and correlation.cross_validated:
        return "synthesize"
    return "deep_dive"
```
When evidence is incomplete, the evaluator produces targeted questions dispatched directly to named specialists. A hard cap of **2 deep dive rounds** prevents unbounded execution.

### 5. Model Profiles & Multi-Tier Fallback Chain
Models are allocated per pipeline phase:
- **Gather / Prefetch:** `gemini-2.5-flash` / `gpt-4o-mini` / `claude-3-5-haiku` (Fast, token-efficient).
- **Specialists:** `gemini-2.5-pro` / `claude-3-7-sonnet` (Balanced reasoning & tool-use).
- **Correlate / Evaluate / Synthesize:** `claude-3-7-sonnet` / `claude-opus` (Deep cross-domain reasoning).

### 6. Production Guardrails & Safe Coercion
- **Duplicate Tool Detector:** SHA-256 hash tracking prevents repeated tool calls with identical arguments.
- **Character Budget Caps:** 50,000 chars per tool result; 800,000 chars cumulative per specialist.
- **Safe Coercion:** Custom Pydantic validators automatically coerce strings like `"<UNKNOWN>"`, `"-"`, `"N/A"` into safe zeros/nulls, preventing schema validation crashes.

### 7. Stateful Post-Investigation Chat
Once the `FinalReport` is assembled and stored in the LangGraph PostgreSQL checkpointer, SRE engineers can chat on the same thread. The Chat Agent retains full incident findings and has active MCP tool access to run live verifications under human direction.

### 8. Continuous 1-5 Star Feedback Loop
Every investigation report and chat turn can be rated (1 to 5 stars + comments) via the feedback API to monitor RCA accuracy over time.

---

## 📂 Project Directory Structure

```text
shepherd/
├── CONTEXT.md                                   # Domain Ubiquitous Language & Glossary
├── Dockerfile                                   # Production container image with embedded kubectl
├── pyproject.toml                               # Package dependencies & tool configs
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
│   └── shepherd/
│       ├── config/                              # Model profiles, limits & environment settings
│       ├── domain/                              # Pydantic schemas, findings & safe coercion
│       ├── mcp/                                 # Domain-scoped MCP clients & composite tools
│       ├── agents/                              # Specialist registry, guardrails & pipeline agents
│       ├── graph/                               # LangGraph state, Send() fan-out & Entry Router
│       └── server/                              # FastAPI REST & feedback endpoints
└── tests/                                       # End-to-end integration & unit test suite
```

---

## 🚀 Getting Started & Installation

### Prerequisites
- Python 3.11+
- (Optional) Docker / Colima / OrbStack & Kind for live Kubernetes E2E testing.
- (Optional) API Keys for Anthropic, OpenAI, or Google Gemini (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`). *If omitted, Shepherd operates in built-in offline simulation mode.*

### Installation

```bash
# Clone repository
git clone https://github.com/netologist/shepherd.git
cd shepherd

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### Running Unit & Integration Tests

```bash
PYTHONPATH=src pytest tests/ -v
```

---

## 💻 Usage Guide

### Python API Usage

```python
import asyncio
from shepherd.graph.router import ShepherdRouter
from shepherd.domain.schemas import InvestigationType

async def run_investigation():
    router = ShepherdRouter()

    # 1. Trigger autonomous investigation
    prompt = "INC-1042: High latency and 5xx errors on checkout-service in namespace prod"
    state = await router.start_investigation(
        raw_input=prompt,
        investigation_type=InvestigationType.INCIDENT_REVIEW,
        investigation_id="inv-demo-1042",
    )

    report = state["final_report"]
    print(f"Primary Root Cause: {report['primary_root_cause']}")
    print(f"Confidence: {report['confidence']} (Cross-Validated: {report['cross_validated']})")

    # 2. Interactive post-investigation chat
    reply = await router.send_chat_message(
        investigation_id="inv-demo-1042",
        message="Which database queries were causing the connection pool starvation?",
    )
    print(f"\nAgent Chat Reply:\n{reply}")

if __name__ == "__main__":
    asyncio.run(run_investigation())
```

---

### FastAPI REST Endpoints

Start the API server:
```bash
uvicorn shepherd.server.app:app --host 0.0.0.0 --port 8000 --reload
```

#### 1. Start an Investigation (`POST /api/v1/investigations`)
```bash
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Content-Type: application/json" \
  -d '{
    "raw_input": "INC-4021: order-api pods failing with CrashLoopBackOff in ecommerce-demo",
    "investigation_type": "incident-review",
    "investigation_id": "inv-4021"
  }'
```

#### 2. Get Investigation Report (`GET /api/v1/investigations/{id}`)
```bash
curl -X GET http://localhost:8000/api/v1/investigations/inv-4021
```

#### 3. Post-Investigation Chat (`POST /api/v1/investigations/{id}/chat`)
```bash
curl -X POST http://localhost:8000/api/v1/investigations/inv-4021/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the memory limit configured on the crashing pod?"}'
```

#### 4. Submit Feedback Rating (`POST /api/v1/feedback`)
```bash
curl -X POST http://localhost:8000/api/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "investigation_id": "inv-4021",
    "rating": 5,
    "comment": "Accurately diagnosed OOMKilled exit code 137.",
    "reviewer": "oncall-sre@company.com"
  }'
```

---

### Interactive Terminal RCA Runner

Run the rich visual investigation terminal script:
```bash
python scripts/run-e2e-incident.py
```

---

## 🚢 End-to-End Testing with Local Kind Cluster

Test Shepherd against a real local Kubernetes cluster simulating an `OOMKilled` microservice failure:

### Step 1: Provision Cluster & Deploy Faulty Microservice
```bash
./scripts/setup-kind-e2e.sh
```
*Creates a `shepherd-e2e` Kind cluster and deploys `order-api` with a `32Mi` limit in namespace `ecommerce-demo`.*

### Step 2: Run Live Multi-Agent Investigation
```bash
python scripts/run-e2e-incident.py
```
*Shepherd connects to the live cluster via `kubectl`, diagnoses exit code 137 (`OOMKilled`), extracts span lock timeouts, synthesizes the cross-validated report, and handles interactive chat.*

### Step 3: Teardown Cluster
```bash
./scripts/cleanup-kind.sh
```

---

## 🔄 CI/CD Automation (GitHub Actions)

- **`.github/workflows/ci.yml`**: Python 3.11/3.12 test matrix + Docker build verification.
- **`.github/workflows/e2e.yml`**: Spawns an ephemeral Kind cluster, deploys the OOM incident scenario, and executes the multi-agent investigation test.

---

## 📚 Architecture Decision Records (ADRs)

Detailed decision records are cataloged in `docs/adr/`:
- [ADR-0001: Architecture Stack (Python, LangGraph & Telemetry MCPs)](docs/adr/0001-architecture-stack-and-langgraph.md)
- [ADR-0002: Domain-Scoped MCP Tooling & Two-Phase Specialists](docs/adr/0002-domain-scoped-mcp-and-two-phase-specialists.md)
- [ADR-0003: Tool-Free Correlation & Deterministic Evaluation Gate](docs/adr/0003-tool-free-correlation-and-deterministic-evaluation-gate.md)
- [ADR-0004: Model Profiles, Fallback Chains & Resilience Guardrails](docs/adr/0004-model-profiles-and-resilience-guardrails.md)
- [ADR-0005: Post-Investigation Chat & Continuous Feedback Loop](docs/adr/0005-post-investigation-chat-and-feedback-loop.md)
- [ADR-0006: Official LangGraph, Pydantic-AI Integration & Evals Suite](docs/adr/0006-official-langgraph-and-pydantic-ai-migration.md)

---

## 📜 References

- *"SRE AI Agents in Trendyol"*. Trendyol Tech, Medium (2026). [Read Article](https://medium.com/trendyol-tech/sre-ai-agents-in-trendyol-098057b9dd31)

---

<div align="center">
<b>Shepherd</b> • Built with ❤️ for SRE & On-Call Engineering Teams
</div>
