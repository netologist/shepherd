"""Synthesize Agent producing the structured FinalReport with multi-tier fallback."""

from datetime import datetime, timezone
import json
import logging
from typing import Any
from sre_ai.domain.schemas import (
    FinalReport,
    IncidentContext,
    CorrelationResult,
    InvestigationType,
    RootCauseCategory,
    ConfidenceLevel,
    RootCauseHypothesis,
    TimelineEvent,
)
from sre_ai.agents.llm_client import UnifiedLLMClient, llm_client
from sre_ai.config.models import get_model_profile

logger = logging.getLogger(__name__)

SYNTHESIZE_SYSTEM_PROMPT = """You are the Synthesize Agent in the SRE AI multi-agent investigation team.
Your responsibility is to assemble the definitive structured incident report (FinalReport) for incident responders.
- Synthesize the primary root cause clearly and rank hypotheses by confidence.
- Construct a detailed evidence chain linking each conclusion to specific telemetry points.
- Provide concrete, actionable immediate and short-term recommendations.
"""


class SynthesizeAgent:
    def __init__(self, client: UnifiedLLMClient | None = None):
        self.client = client or llm_client

    async def execute(
        self,
        investigation_id: str,
        investigation_type: InvestigationType,
        context: IncidentContext,
        correlation: CorrelationResult | None,
        findings_by_domain: dict[str, Any],
        deep_dive_count: int = 0,
    ) -> FinalReport:
        """Assembles FinalReport with multi-model fallback and deterministic template safety."""
        profile = get_model_profile(investigation_type)

        payload = {
            "investigation_id": investigation_id,
            "incident_context": context.model_dump(),
            "correlation": correlation.model_dump() if correlation else None,
            "specialist_findings": findings_by_domain,
            "deep_dive_count": deep_dive_count,
        }

        messages = [
            {"role": "system", "content": SYNTHESIZE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Compile the FinalReport from this investigation state:\n```json\n{json.dumps(payload, indent=2, default=str)}\n```"},
        ]

        try:
            report = await self.client.invoke_structured_output(
                schema=FinalReport,
                messages=messages,
                model=profile.synthesize_model,
                fallback_models=profile.fallback_chain,
            )
            # Ensure metadata consistency
            report.investigation_id = investigation_id
            report.incident_id = context.incident_id or "UNKNOWN"
            report.investigation_type = investigation_type
            report.deep_dive_count = deep_dive_count
            return report
        except Exception as exc:
            logger.error("Synthesize LLM chain failed (%s); generating deterministic fallback report", exc)
            return self._fallback_report(investigation_id, investigation_type, context, correlation, findings_by_domain, deep_dive_count)

    def _fallback_report(
        self,
        investigation_id: str,
        investigation_type: InvestigationType,
        context: IncidentContext,
        correlation: CorrelationResult | None,
        findings_by_domain: dict[str, Any],
        deep_dive_count: int,
    ) -> FinalReport:
        """Deterministic raw-findings fallback report guaranteed to succeed without LLM."""
        primary_rc = "Service degradation detected across telemetry sources."
        category = RootCauseCategory.UNKNOWN
        confidence = ConfidenceLevel.LOW
        cross_val = False
        timeline: list[TimelineEvent] = []
        evidence: list[str] = []

        if correlation:
            primary_rc = correlation.root_cause_summary
            category = correlation.category
            confidence = correlation.confidence
            cross_val = correlation.cross_validated
            timeline = correlation.timeline
            evidence = correlation.contributing_factors

        # Extract domain signals if timeline is empty
        for domain, f in findings_by_domain.items():
            if isinstance(f, dict):
                summary = f.get("summary") or f"Telemetry captured in {domain} domain."
                evidence.append(f"[{domain.upper()}]: {summary}")

        return FinalReport(
            investigation_id=investigation_id,
            incident_id=context.incident_id or "UNKNOWN",
            investigation_type=investigation_type,
            primary_root_cause=primary_rc,
            category=category,
            confidence=confidence,
            cross_validated=cross_val,
            root_cause_hypotheses=[
                RootCauseHypothesis(
                    title="Primary RCA Hypothesis",
                    description=primary_rc,
                    category=category,
                    confidence=confidence,
                    evidence=evidence[:5],
                )
            ],
            evidence_chain=evidence,
            timeline=timeline,
            impact_analysis=f"Incident {context.incident_id or 'UNKNOWN'} analyzed with {len(findings_by_domain)} domain specialist(s).",
            contributing_factors=evidence[:3],
            immediate_recommendations=["Review telemetry logs and restart suspect pods if degraded."],
            short_term_recommendations=["Conduct comprehensive post-mortem review."],
            deep_dive_count=deep_dive_count,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
