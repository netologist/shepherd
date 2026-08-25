"""Playbook/Runbook Specialist — thin adapter over PlaybookRunbookAgent.

Unlike telemetry specialists (metrics, traces, k8s), this specialist does NOT
use the two-phase MCP tool loop.  LlamaIndex ReActAgent manages its own
reasoning loop internally.  We override `execute` and bypass the base class.
"""

from __future__ import annotations

import logging
from typing import Any

from shepherd.agents.playbook_runbook import PlaybookRunbookAgent
from shepherd.agents.specialists.base import BaseSpecialist
from shepherd.domain.schemas import (
    CorrelationResult,
    IncidentContext,
    InvestigationBrief,
    PlaybookFindings,
)
from shepherd.mcp.base import DomainMCPClient

logger = logging.getLogger(__name__)


class _NullMCPClient(DomainMCPClient):
    """Placeholder MCP client — PlaybookSpecialist does not use MCP tools directly."""

    def __init__(self) -> None:
        super().__init__(domain="playbook")


_PLAYBOOK_SYSTEM_PROMPT = (
    "You are the Playbook/Runbook Specialist. "
    "Use the LlamaIndex ReActAgent to match incidents to SRE runbooks."
)


class PlaybookSpecialist(BaseSpecialist):
    """Specialist that wraps PlaybookRunbookAgent and returns PlaybookFindings."""

    def __init__(self) -> None:
        super().__init__(
            domain="playbook",
            mcp_client=_NullMCPClient(),
            findings_schema=PlaybookFindings,
            system_prompt=_PLAYBOOK_SYSTEM_PROMPT,
        )
        self._agent: PlaybookRunbookAgent = PlaybookRunbookAgent()

    async def execute(  # type: ignore[override]
        self,
        brief: InvestigationBrief,
        prefetched_data: dict[str, Any] | None = None,  # noqa: ARG002
        additional_instructions: str | None = None,
        model: str = "anthropic/claude-3-5-haiku-20241022",  # noqa: ARG002
        fallback_models: list[str] | None = None,  # noqa: ARG002
    ) -> PlaybookFindings:
        """Delegate directly to PlaybookRunbookAgent; bypass the MCP tool-loop."""
        context = IncidentContext(
            incident_id=brief.incident_id,
            service_name=brief.focus_areas[0] if brief.focus_areas else None,
            raw_text=additional_instructions or brief.summary,
        )
        # Correlation result is not available at initial dispatch time.
        # PlaybookRunbookAgent falls back to the raw_text / incident_id context.
        correlation: CorrelationResult | None = None

        try:
            return await self._agent.execute(context=context, correlation=correlation)
        except Exception as exc:
            logger.error("PlaybookSpecialist.execute failed: %s", exc)
            return PlaybookFindings(
                incident_summary=brief.summary,
                notes=[f"Playbook lookup failed: {exc}"],
            )
