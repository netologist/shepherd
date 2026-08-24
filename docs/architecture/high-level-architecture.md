# High-Level Architecture: Shepherd

## 1. System Overview

Shepherd is an automated root-cause analysis (RCA) and troubleshooting platform designed to investigate production incidents, correlate cross-domain telemetry, and produce structured incident reports without human intervention. Once an investigation is complete, it transitions into an interactive post-investigation assistant.

The system is **not a Kubernetes Operator** (it does not manage custom resource definitions or execute mutating reconciliation loops). Instead, it runs as a containerized service (FastAPI application + background async workers) with read-only access to external observability backends and infrastructure APIs.

```mermaid
flowchart TD
    subgraph TriggerSources["1. Trigger Sources"]
        Inc["Incident Management (PagerDuty / Opsgenie / Webhook)"]
        Alert["Alertmanager / Anomaly Detector"]
        UI["SRE Portal / CLI / Slack Bot"]
    end

    subgraph CoreEngine["2. SRE AI Core Engine (Python / LangGraph)"]
        EntryRouter["Entry Router"]
        Prefetch["Prefetch & Regex Extraction"]
        GatherAgent["Gather Agent"]
        
        subgraph ParallelSpecialists["Specialist Fan-Out (LangGraph Send)"]
            MetricsSpec["Metrics Specialist"]
            TracesSpec["Traces Specialist"]
            K8sSpec["Kubernetes Specialist"]
            TroubleshootSpec["Troubleshoot Specialist"]
            TopologySpec["CUJ / Topology Specialist"]
            ExtSpec["External Platform Agents"]
        end
        
        CorrelateAgent["Correlate Agent (Tool-Free)"]
        EvaluateGate{"Deterministic Evaluation Gate"}
        DeepDiveAgent["Deep Dive Dispatcher (Max 2 Rounds)"]
        SynthesizeAgent["Synthesize Agent (Report Generator)"]
        ChatAgent["Post-Investigation Chat Agent (Tool-Enabled)"]
    end

    subgraph TelemetryMCP["3. Domain-Scoped MCP Tooling Layer"]
        MetricsMCP["metrics-mcp (Prometheus / PromQL)"]
        TracesMCP["traces-mcp (Jaeger / OpenTelemetry)"]
        K8sMCP["k8s-mcp (Kubernetes API - Read Only)"]
        TroubleshootMCP["troubleshoot-mcp (Pre-check Reports)"]
    end

    subgraph StatePersistence["4. State & Checkpoints"]
        PG[("PostgreSQL Checkpointer (Thread State)")]
        ReviewDB[("Feedback & Evaluation Store")]
    end

    %% Wiring
    TriggerSources -->|HTTP / Webhook| EntryRouter
    EntryRouter -->|New Investigation| Prefetch
    EntryRouter -->|Follow-up Message| ChatAgent
    Prefetch --> GatherAgent
    GatherAgent -->|Investigation Brief| ParallelSpecialists
    
    MetricsSpec <--> MetricsMCP
    TracesSpec <--> TracesMCP
    K8sSpec <--> K8sMCP
    TroubleshootSpec <--> TroubleshootMCP
    
    ParallelSpecialists -->|Typed Findings| CorrelateAgent
    CorrelateAgent -->|Correlation Result| EvaluateGate
    
    EvaluateGate -->|Confidence < High OR Not Cross-Validated| DeepDiveAgent
    DeepDiveAgent -->|Targeted Instructions| ParallelSpecialists
    EvaluateGate -->|Confidence == High AND Cross-Validated OR Max Deep-Dives Hit| SynthesizeAgent
    
    SynthesizeAgent -->|Final Report| PG
    ChatAgent <--> PG
    ChatAgent <--> TelemetryMCP
    UI -.->|1-5 Star Rating| ReviewDB
```

---

## 2. Key Components & Responsibilities

| Component | Responsibility | Tool Access |
|---|---|---|
| **Entry Router** | Inspects thread ID and determines whether to start a new investigation or route to existing post-investigation chat. | No |
| **Gather Agent & Prefetch** | Extracts incident/troubleshooting IDs via regex, prefetches initial summaries, and outputs an `InvestigationBrief`. | Prefetch MCPs only |
| **Specialist Agents** | Domain-isolated investigators running a 10-15 turn tool loop followed by structured Pydantic extraction. | Domain-scoped MCP |
| **Correlate Agent** | Cross-references findings across independent specialists to filter false-positive noise and confirm root-cause convergence. | **None (Zero Tool Access)** |
| **Evaluation Gate** | Pure deterministic Python function applying cross-validation rules and bounding deep dives to $\le 2$ rounds. | **None** |
| **Deep Dive Agent** | Generates targeted follow-up questions for named specialists to fill specific evidence gaps. | **None** |
| **Synthesize Agent** | Assembles the final structured incident report with timeline, evidence chain, and actionable recommendations. | **None** |
| **Chat Agent** | Allows SRE engineers to interrogate the investigation report, re-run specialists, or perform live checks. | Full Telemetry MCPs |

---

## 3. Telemetry & Data Boundaries

- **Kubernetes Access:** Restricted to read-only API permissions (`get`, `list`, `watch` on Pods, Nodes, Events, Deployments, StatefulSets, HPAs, and ResourceMetrics).
- **Metrics Access:** Scoped PromQL queries against Prometheus / Thanos / VictoriaMetrics with per-query time bounds.
- **Trace Access:** Span filtering against Jaeger / OpenTelemetry collectors matching affected service namespaces and time windows.
- **Markdown Optimization:** All MCP endpoints format results in dense, structured Markdown rather than raw verbose JSON, reducing token consumption by ~40%.
