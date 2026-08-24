"""State definitions and reducers for LangGraph execution."""

from typing import Annotated, Any, TypedDict
from sre_ai.domain.schemas import (
    IncidentContext,
    InvestigationBrief,
    CorrelationResult,
    FinalReport,
    InvestigationType,
)


def last_non_none(current: Any, update: Any) -> Any:
    """Last-writer-wins reducer for parallel specialist state keys."""
    return update if update is not None else current


def merge_dict_reducer(current: dict[str, Any] | None, update: dict[str, Any] | None) -> dict[str, Any]:
    """Merges dictionary outputs from parallel specialists into a combined dict."""
    result = dict(current or {})
    if update:
        result.update(update)
    return result


class SpecialistDispatch(TypedDict):
    """Payload passed to run_specialist via Send()."""
    domain: str
    brief: dict[str, Any]
    prefetched_data: dict[str, Any]
    additional_instructions: str | None


class InvestigationState(TypedDict):
    investigation_id: str
    investigation_type: str
    raw_input: str
    incident_context: Annotated[dict[str, Any] | None, last_non_none]
    investigation_brief: Annotated[dict[str, Any] | None, last_non_none]
    prefetched_data: Annotated[dict[str, str], merge_dict_reducer]
    findings_by_domain: Annotated[dict[str, Any], merge_dict_reducer]
    correlation_result: Annotated[dict[str, Any] | None, last_non_none]
    evaluation_result: Annotated[dict[str, Any] | None, last_non_none]
    deep_dive_count: Annotated[int, last_non_none]
    suggested_deep_dives: Annotated[list[dict[str, Any]], last_non_none]
    final_report: Annotated[dict[str, Any] | None, last_non_none]
    chat_history: Annotated[list[dict[str, str]], last_non_none]
    current_phase: Annotated[str, last_non_none]
