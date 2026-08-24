"""Evaluate Agent & Deterministic Evaluation Gate."""

import json
from typing import Any
from pydantic import BaseModel, Field
from shepherd.domain.schemas import (
    CorrelationResult,
    ConfidenceLevel,
    DeepDiveTask,
    InvestigationType,
)
from shepherd.agents.llm_client import UnifiedLLMClient, llm_client
from shepherd.config.models import get_model_profile

MAX_DEEP_DIVE_ROUNDS = 2

EVALUATE_SYSTEM_PROMPT = """You are the Evaluate Agent in the SRE AI multi-agent investigation team.
Your responsibility is to critically assess the correlation hypothesis.
- If the hypothesis is well-evidenced and cross-validated across independent specialists, confirm it.
- If the hypothesis lacks definitive evidence (e.g. error rate high in metrics but no failing spans found in traces), generate targeted, concrete questions for specific specialists in `suggested_deep_dives`.
- Name canonical specialist keys: `metrics`, `traces`, `kubernetes`, `troubleshoot`.
"""


class EvaluationResult(BaseModel):
    is_sufficient: bool = Field(description="True if hypothesis is ready for final report")
    reasoning: str = Field(description="Explanation of evaluation evaluation")
    suggested_deep_dives: list[DeepDiveTask] = Field(
        default_factory=list,
        description="Targeted tasks for specific specialists if more evidence is needed",
    )


class EvaluateAgent:
    def __init__(self, client: UnifiedLLMClient | None = None):
        self.client = client or llm_client

    async def execute(
        self,
        investigation_type: InvestigationType,
        correlation: CorrelationResult,
        findings_by_domain: dict[str, Any],
    ) -> EvaluationResult:
        """Evaluates hypothesis quality and proposes deep dive tasks if gaps exist."""
        # If already high confidence and cross-validated, skip deep dive generation
        if correlation.confidence == ConfidenceLevel.HIGH and correlation.cross_validated:
            return EvaluationResult(
                is_sufficient=True,
                reasoning="RCA is well-grounded and cross-validated by independent specialists.",
                suggested_deep_dives=[],
            )

        profile = get_model_profile(investigation_type)
        payload = {
            "correlation": correlation.model_dump(),
            "specialist_findings": findings_by_domain,
        }

        messages = [
            {"role": "system", "content": EVALUATE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Assess this investigation state:\n```json\n{json.dumps(payload, indent=2, default=str)}\n```"},
        ]

        result = await self.client.invoke_structured_output(
            schema=EvaluationResult,
            messages=messages,
            model=profile.evaluate_model,
            fallback_models=profile.fallback_chain,
        )

        return result


def route_after_evaluation(
    correlation: CorrelationResult | None,
    deep_dive_count: int,
    max_deep_dives: int = MAX_DEEP_DIVE_ROUNDS,
) -> str:
    """Pure deterministic routing function. No LLM decides control flow."""
    if deep_dive_count >= max_deep_dives:
        return "synthesize"

    if correlation and correlation.confidence == ConfidenceLevel.HIGH and correlation.cross_validated:
        return "synthesize"

    return "deep_dive"
