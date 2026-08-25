"""Graph builder for SRE AI multi-agent investigation pipeline."""

import asyncio
import logging
from typing import Any
from shepherd.domain.schemas import (
    IncidentContext,
    InvestigationBrief,
    CorrelationResult,
    InvestigationType,
    DeepDiveTask,
)
from shepherd.graph.state import InvestigationState, SpecialistDispatch
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from shepherd.agents.gather import GatherAgent
from shepherd.agents.specialists.registry import specialist_registry
from shepherd.agents.correlate import CorrelateAgent
from shepherd.agents.evaluate import EvaluateAgent, route_after_evaluation
from shepherd.agents.deep_dive import DeepDiveDispatcher
from shepherd.agents.synthesize import SynthesizeAgent

logger = logging.getLogger(__name__)


async def gather_node(state: InvestigationState) -> dict[str, Any]:
    """Extracts context, prefetches data, and generates investigation brief."""
    raw_input = state.get("raw_input", "")
    inv_type_str = state.get("investigation_type", InvestigationType.INCIDENT_REVIEW.value)
    try:
        inv_type = InvestigationType(inv_type_str)
    except ValueError:
        inv_type = InvestigationType.INCIDENT_REVIEW

    gather_agent = GatherAgent()
    context, brief, prefetched = await gather_agent.execute(raw_input, inv_type)

    return {
        "incident_context": context.model_dump(),
        "investigation_brief": brief.model_dump(),
        "prefetched_data": prefetched,
        "current_phase": "gather_complete",
    }


def route_to_specialists(state: InvestigationState) -> list[Send]:
    """Fans out to domain specialists in parallel using Send()."""
    brief_dict = state.get("investigation_brief") or {}
    prefetched = state.get("prefetched_data") or {}

    # Identify domains to dispatch
    suspected = brief_dict.get("suspected_domains") or []
    if not suspected:
        # Default core four specialists
        domains_to_run = ["metrics", "traces", "kubernetes", "troubleshoot"]
    else:
        domains_to_run = [specialist_registry.normalize_name(d) for d in suspected]

    dispatches: list[Send] = []
    for domain in domains_to_run:
        payload: SpecialistDispatch = {
            "domain": domain,
            "brief": brief_dict,
            "prefetched_data": prefetched,
            "additional_instructions": None,
        }
        dispatches.append(Send(node="run_specialist", arg=payload))

    return dispatches


async def run_specialist_node(dispatch: SpecialistDispatch) -> dict[str, Any]:
    """Runs a single domain specialist with two-phase execution."""
    domain = dispatch["domain"]
    brief_data = dispatch["brief"]
    prefetched = dispatch.get("prefetched_data", {})
    instructions = dispatch.get("additional_instructions")

    specialist = specialist_registry.get_specialist(domain)
    if not specialist:
        logger.warning("Specialist for domain '%s' not registered", domain)
        return {"findings_by_domain": {domain: {"summary": f"Specialist '{domain}' not found."}}}

    brief = InvestigationBrief.model_validate(brief_data)
    findings = await specialist.execute(
        brief=brief,
        prefetched_data=prefetched,
        additional_instructions=instructions,
    )

    return {
        "findings_by_domain": {domain: findings.model_dump()},
    }


async def correlate_node(state: InvestigationState) -> dict[str, Any]:
    """Correlates structured findings from all specialists without tool access."""
    inv_type_str = state.get("investigation_type", InvestigationType.INCIDENT_REVIEW.value)
    try:
        inv_type = InvestigationType(inv_type_str)
    except ValueError:
        inv_type = InvestigationType.INCIDENT_REVIEW

    findings = state.get("findings_by_domain") or {}
    correlator = CorrelateAgent()
    correlation = await correlator.execute(inv_type, findings)

    return {
        "correlation_result": correlation.model_dump(),
        "current_phase": "correlation_complete",
    }


async def evaluate_node(state: InvestigationState) -> dict[str, Any]:
    """Evaluates correlation hypothesis and generates suggested deep dives if needed."""
    inv_type_str = state.get("investigation_type", InvestigationType.INCIDENT_REVIEW.value)
    try:
        inv_type = InvestigationType(inv_type_str)
    except ValueError:
        inv_type = InvestigationType.INCIDENT_REVIEW

    correlation_data = state.get("correlation_result")
    correlation = CorrelationResult.model_validate(correlation_data) if correlation_data else None
    findings = state.get("findings_by_domain") or {}

    evaluator = EvaluateAgent()
    if correlation:
        eval_res = await evaluator.execute(inv_type, correlation, findings)
        return {
            "evaluation_result": eval_res.model_dump(),
            "suggested_deep_dives": [t.model_dump() for t in eval_res.suggested_deep_dives],
            "current_phase": "evaluation_complete",
        }

    return {
        "evaluation_result": {"is_sufficient": False, "reasoning": "Missing correlation result", "suggested_deep_dives": []},
        "suggested_deep_dives": [],
        "current_phase": "evaluation_failed",
    }


def evaluate_gate_router(state: InvestigationState) -> str:
    """Pure deterministic routing function checking confidence, cross-validation, and deep dive count."""
    correlation_data = state.get("correlation_result")
    correlation = CorrelationResult.model_validate(correlation_data) if correlation_data else None
    deep_dive_count = state.get("deep_dive_count", 0)

    return route_after_evaluation(correlation, deep_dive_count)


async def deep_dive_node(state: InvestigationState) -> dict[str, Any]:
    """Executes targeted deep dives for named specialists and increments deep_dive_count."""
    tasks_data = state.get("suggested_deep_dives") or []
    brief_data = state.get("investigation_brief") or {}
    prefetched = state.get("prefetched_data") or {}
    deep_dive_count = state.get("deep_dive_count", 0) + 1

    # Execute deep dive dispatches directly
    dispatches = DeepDiveDispatcher.prepare_deep_dive_targets(
        [DeepDiveTask.model_validate(t) if isinstance(t, dict) else t for t in tasks_data]
    )

    deep_dive_tasks = []
    for d in dispatches:
        payload: SpecialistDispatch = {
            "domain": d["domain"],
            "brief": brief_data,
            "prefetched_data": prefetched,
            "additional_instructions": d["additional_instructions"],
        }
        deep_dive_tasks.append(run_specialist_node(payload))

    if deep_dive_tasks:
        results = await asyncio.gather(*deep_dive_tasks, return_exceptions=True)
        merged_findings = dict(state.get("findings_by_domain") or {})
        for res in results:
            if isinstance(res, dict) and "findings_by_domain" in res:
                merged_findings.update(res["findings_by_domain"])

        return {
            "deep_dive_count": deep_dive_count,
            "findings_by_domain": merged_findings,
            "current_phase": f"deep_dive_round_{deep_dive_count}_complete",
        }

    return {
        "deep_dive_count": deep_dive_count,
        "current_phase": f"deep_dive_round_{deep_dive_count}_empty",
    }


async def synthesize_node(state: InvestigationState) -> dict[str, Any]:
    """Generates the structured FinalReport."""
    inv_id = state.get("investigation_id", "inv-default")
    inv_type_str = state.get("investigation_type", InvestigationType.INCIDENT_REVIEW.value)
    try:
        inv_type = InvestigationType(inv_type_str)
    except ValueError:
        inv_type = InvestigationType.INCIDENT_REVIEW

    ctx_data = state.get("incident_context") or {}
    context = IncidentContext.model_validate(ctx_data)
    corr_data = state.get("correlation_result")
    correlation = CorrelationResult.model_validate(corr_data) if corr_data else None
    findings = state.get("findings_by_domain") or {}
    deep_dive_count = state.get("deep_dive_count", 0)

    synthesizer = SynthesizeAgent()
    report = await synthesizer.execute(
        investigation_id=inv_id,
        investigation_type=inv_type,
        context=context,
        correlation=correlation,
        findings_by_domain=findings,
        deep_dive_count=deep_dive_count,
    )

    return {
        "final_report": report.model_dump(),
        "current_phase": "investigation_complete",
    }


def build_investigation_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """Builds and compiles the SRE AI LangGraph investigation pipeline."""
    graph = StateGraph(InvestigationState)

    # Register nodes
    graph.add_node("gather", gather_node)
    graph.add_node("run_specialist", run_specialist_node)
    graph.add_node("correlate", correlate_node)
    graph.add_node("evaluate", evaluate_node)
    graph.add_node("deep_dive", deep_dive_node)
    graph.add_node("synthesize", synthesize_node)

    # Entry edge
    graph.add_edge(START, "gather")

    # Gather fans out to specialists via Send()
    graph.add_conditional_edges("gather", route_to_specialists, ["run_specialist"])

    # Specialist outputs flow into correlation
    graph.add_edge("run_specialist", "correlate")

    # Correlate moves to evaluate
    graph.add_edge("correlate", "evaluate")

    # Evaluate uses deterministic evaluation gate router
    graph.add_conditional_edges(
        "evaluate",
        evaluate_gate_router,
        {
            "synthesize": "synthesize",
            "deep_dive": "deep_dive",
        },
    )

    # Deep dive loops back to correlate for re-synthesis
    graph.add_edge("deep_dive", "correlate")

    # Synthesize completes graph
    graph.add_edge("synthesize", END)

    return graph.compile(checkpointer=checkpointer)
