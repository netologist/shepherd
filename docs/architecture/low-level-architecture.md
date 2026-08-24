# Low-Level Architecture & Technical Specification

## 1. LangGraph State Schema & Reducers

LangGraph state is shared across parallel nodes via custom reducers to prevent `InvalidUpdateError` during parallel fan-out (`Send()`).

```mermaid
classDiagram
    class InvestigationState {
        +str investigation_id
        +InvestigationType investigation_type
        +str raw_input
        +IncidentContext incident_context
        +InvestigationBrief investigation_brief
        +MetricsFindings metrics_findings
        +TraceFindings trace_findings
        +KubernetesFindings kubernetes_findings
        +TroubleshootFindings troubleshoot_findings
        +dict external_findings
        +CorrelationResult correlation_result
        +int deep_dive_count
        +list[DeepDiveTask] suggested_deep_dives
        +FinalReport final_report
        +list[BaseMessage] messages
        +str current_phase
    }

    class MetricsFindings {
        +str service_name
        +float error_rate_pct
        +float p99_latency_ms
        +list[str] anomalous_metrics
        +list[str] evidence_urls
    }

    class TraceFindings {
        +list[str] failing_spans
        +str root_span_service
        +str root_error_message
        +float avg_duration_ms
    }

    class KubernetesFindings {
        +list[str] oom_killed_pods
        +list[str] restarting_pods
        +list[str] unhealthy_nodes
        +list[str] warning_events
    }

    class CorrelationResult {
        +str root_cause_summary
        +RootCauseCategory category
        +float confidence_score
        +bool cross_validated
        +list[str] validated_by_specialists
        +list[TimelineEvent] timeline
        +list[str] contributing_factors
    }

    InvestigationState *-- MetricsFindings
    InvestigationState *-- TraceFindings
    InvestigationState *-- KubernetesFindings
    InvestigationState *-- CorrelationResult
```

### LangGraph State Reducer Definition

```python
from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

def last_non_none(current: any, update: any) -> any:
    """Last-writer-wins reducer for parallel specialist state keys."""
    return update if update is not None else current

class InvestigationState(TypedDict):
    investigation_id: str
    investigation_type: str
    incident_context: Annotated[dict | None, last_non_none]
    investigation_brief: Annotated[dict | None, last_non_none]
    metrics_findings: Annotated[dict | None, last_non_none]
    trace_findings: Annotated[dict | None, last_non_none]
    kubernetes_findings: Annotated[dict | None, last_non_none]
    troubleshoot_findings: Annotated[dict | None, last_non_none]
    external_findings: Annotated[dict, last_non_none]
    correlation_result: Annotated[dict | None, last_non_none]
    deep_dive_count: Annotated[int, last_non_none]
    suggested_deep_dives: Annotated[list[dict], last_non_none]
    final_report: Annotated[dict | None, last_non_none]
    messages: Annotated[list[BaseMessage], add_messages]
    current_phase: Annotated[str, last_non_none]
```

---

## 2. Detailed Execution Sequence & Node Logic

```mermaid
sequenceDiagram
    autonumber
    actor Caller as Incident Platform / SRE
    participant Router as Entry Router
    participant Gather as Gather Node
    participant Specs as Parallel Specialists (Send Fan-Out)
    participant MCP as Domain MCP Servers
    participant Correlate as Correlate Node (Tool-Free)
    participant EvalGate as Evaluation Gate (Python if/else)
    participant DeepDive as Deep Dive Node
    participant Synth as Synthesize Node (Multi-Model Fallback)
    participant PG as PostgreSQL Checkpoint

    Caller->>Router: POST /investigate (incident_id="INC-1042")
    Router->>Gather: New thread_id
    Gather->>MCP: Prefetch incident & troubleshoot details
    MCP-->>Gather: Normalized incident metadata
    Gather->>Gather: LLM structured extraction -> InvestigationBrief
    
    par Fan-Out via Send("run_specialist")
        Gather->>Specs: Metrics Specialist (Brief + Prefetch)
        Gather->>Specs: Traces Specialist (Brief + Prefetch)
        Gather->>Specs: Kubernetes Specialist (Brief + Prefetch)
        Gather->>Specs: Troubleshoot Specialist (Brief + Prefetch)
    end
    
    loop Phase 1: Tool Loop (Max 15 iterations)
        Specs->>MCP: Call Composite / Domain Tools
        MCP-->>Specs: Markdown Telemetry Payload
    end
    
    Specs->>Specs: Phase 2: Structured Pydantic Extraction (Tool-Free LLM)
    Specs->>Correlate: Merge findings into state
    
    Note over Correlate: Tool-Free LLM Reasoning
    Correlate->>Correlate: Correlate cross-domain signals (Category, Timeline, Confidence)
    Correlate->>EvalGate: CorrelationResult
    
    alt confidence == 'high' AND cross_validated == True (OR deep_dive_count >= 2)
        EvalGate->>Synth: Proceed to Synthesis
        Synth->>Synth: Primary LLM -> Fallback LLM -> Deterministic Template
        Synth->>PG: Save FinalReport to Checkpoint
        Synth-->>Caller: FinalReport Response
    else confidence < 'high' OR cross_validated == False
        EvalGate->>DeepDive: Trigger Deep Dive (Round < 2)
        DeepDive->>DeepDive: Generate specific questions for named specialists
        DeepDive->>Specs: Dispatch targeted follow-up via Send()
        Specs->>Correlate: Loop back with enriched findings
    end
```

---

## 3. Production Hardening Mechanisms

```mermaid
flowchart LR
    subgraph Guardrails["Specialist Guardrails Middleware"]
        DupCheck["Duplicate Tool Call Filter<br/>(Cache hash check)"]
        SizeCap["Character Budget Cap<br/>(50KB/call, 800KB total)"]
        IterLimit["Max Iteration Breaker<br/>(10-15 steps -> strip tools)"]
        Coercion["Safe Type Coercion<br/>('N/A', 'unknown' -> 0/null)"]
    end

    subgraph LLMResilience["LLM Fallback Chain"]
        Primary["Tier 1: Primary Model<br/>(e.g. Claude 3.7 Sonnet / Gemini Pro)"]
        Secondary["Tier 2: Fallback Model<br/>(e.g. GPT-4o / Gemini Flash)"]
        RawFallback["Tier 3: Deterministic Fallback<br/>(Pydantic template from raw findings)"]
    end

    Guardrails --> LLMResilience
```

1. **Duplicate Tool Call Filter:** Computes SHA-256 of `(tool_name, sorted_json_args)`. If re-issued, immediately returns: `"Error: Duplicate call suppressed. Refer to prior result."`
2. **Character Budget:** Per-result cap of 50,000 characters; cumulative session cap of 800,000 characters. When exceeded, tool bindings are removed, forcing immediate conclusion.
3. **Safe Coercion Validators:** Pydantic models use `@field_validator(mode="before")` on float/integer fields to safely map `"<UNKNOWN>"`, `"-"`, `"N/A"` to `0` or `None`.
4. **Three-Way Race Cancellation:** Every async node execution races against an `asyncio.Event` triggered by user cancellation or wall-clock timeouts.
