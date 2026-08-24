# Shepherd: SRE Incident Investigation

An automated multi-agent incident investigation system that automates root cause analysis (RCA), separates symptoms from causes, and enables post-investigation chat for SRE and on-call teams.

## Language

**Investigation**:
An automated, end-to-end execution of the agent pipeline triggered by an incident or alert to determine root cause.
_Avoid_: Run, job, session (when referring to the full investigation lifecycle)

**Investigation Type**:
A predefined operational mode (e.g. incident-review, oncall-alert-analyzer, qa-support) that dictates the prompt profile, active specialists, and tool quotas.
_Avoid_: Workflow type, investigation mode

**Investigation Brief**:
A structured briefing produced by the Gather Agent that defines the scope, focus areas, and explicit exclusions for specialists.
_Avoid_: Prompt context, task description

**Composite Tool**:
An aggregated MCP tool (e.g. `diagnose_pod`, `application_perf_overview`) that bundles multiple atomic telemetry queries into a single normalized markdown response.
_Avoid_: Multi-tool, macro, compound query

**Structured Extraction**:
The second phase of specialist execution where free-form tool interactions are converted into a typed Pydantic finding without tool bindings.
_Avoid_: Parsing, output formatting, summarization

**Specialist Registry**:
A configuration-driven registry that discovers, initializes, and dispatches native and external domain specialist agents without modifying graph topology.
_Avoid_: Plugin manager, agent loader

**Specialist**:
A domain-specific sub-agent (e.g. metrics, traces, kubernetes, troubleshoot) executing a bounded tool loop followed by structured findings extraction.
_Avoid_: Worker, subagent, tool-runner

**Finding**:
A typed, structured domain observation extracted by a specialist at the end of its tool-use loop.
_Avoid_: Result, output, log summary

**Correlate**:
The tool-free synthesis node that matches findings across multiple independent specialists to generate a cross-validated RCA hypothesis.
_Avoid_: Aggregator, merger

**Cross-Validation**:
Verification of a root-cause hypothesis corroborated by at least two independent specialists.
_Avoid_: Multi-source check, consensus


**Evaluation Gate**:
A deterministic routing check (`route_after_evaluation`) that inspects confidence and cross-validation flags to decide between deep-dive re-investigation or final synthesis.
_Avoid_: Decision maker, router agent, LLM judge

**Correlation Rule**:
The requirement that a primary root cause hypothesis must be independently corroborated by at least two distinct specialist findings.
_Avoid_: Heuristic, correlation logic
**Deep Dive**:
A targeted, iterative re-investigation loop dispatched with specific questions to named specialists when confidence or cross-validation is insufficient.
_Avoid_: Retry, second-pass, drill-down

**Model Profile**:
A configuration mapping specific pipeline phases (gather, specialists, correlate, synthesize) and investigation types to designated LLM tiers (fast, balanced, deep-reasoning).
_Avoid_: LLM config, model settings

**Fallback Report**:
A deterministic, non-LLM incident report generated directly from raw specialist findings when all configured LLM providers fail.
_Avoid_: Error report, backup report

**Safe Coercion**:
Custom schema validators that convert non-standard LLM string inputs (e.g. "N/A", "unknown") into safe zero/null defaults without failing validation.
_Avoid_: Type casting, sanitization

**Specialist Guardrails**:
Runtime limits (duplicate call detection, per-result size caps, max iterations) enforced to prevent runaway agent tool loops.
_Avoid_: Rate limiter, execution filter

**Entry Router**:
A dispatch router that directs incoming user requests either to a new investigation pipeline or to an existing post-investigation chat session based on checkpoint state.
_Avoid_: Request handler, gateway

**Post-Investigation Chat**:
An interactive conversational phase maintaining full incident context and live MCP access to answer follow-up queries or re-trigger focused specialist checks.
_Avoid_: Chat mode, SRE assistant

**Feedback Review**:
A 1-to-5 star rating and commentary captured per investigation/message to track RCA quality and identify weak prompts or tool gaps.
_Avoid_: Rating, user feedback

**Final Report**:
A structured incident report containing ranked root cause hypotheses, evidence chain, timeline, impact analysis, and actionable recommendations.
_Avoid_: Summary, RCA document
