"""Tests for Correlate, Evaluate Gate, and Deep Dive routing."""

import pytest
from sre_ai.domain.schemas import (
    CorrelationResult,
    ConfidenceLevel,
    RootCauseCategory,
    InvestigationType,
)
from sre_ai.agents.evaluate import route_after_evaluation
from sre_ai.agents.correlate import CorrelateAgent


def test_evaluate_gate_deterministic_routing():
    # Scenario 1: High confidence & cross-validated -> synthesize
    corr_high = CorrelationResult(
        root_cause_summary="DB pool starvation",
        category=RootCauseCategory.DATABASE,
        confidence=ConfidenceLevel.HIGH,
        cross_validated=True,
    )
    assert route_after_evaluation(corr_high, deep_dive_count=0) == "synthesize"

    # Scenario 2: Low confidence / unvalidated -> deep_dive (under cap)
    corr_low = CorrelationResult(
        root_cause_summary="Suspect network timeout",
        category=RootCauseCategory.INFRASTRUCTURE,
        confidence=ConfidenceLevel.LOW,
        cross_validated=False,
    )
    assert route_after_evaluation(corr_low, deep_dive_count=0) == "deep_dive"
    assert route_after_evaluation(corr_low, deep_dive_count=1) == "deep_dive"

    # Scenario 3: Cap reached (deep_dive_count >= 2) -> synthesize regardless of confidence
    assert route_after_evaluation(corr_low, deep_dive_count=2) == "synthesize"
    assert route_after_evaluation(corr_low, deep_dive_count=3) == "synthesize"


@pytest.mark.asyncio
async def test_cluster_resource_deterministic_passthrough():
    correlator = CorrelateAgent()
    findings = {
        "kubernetes": {
            "oom_killed_pods": ["checkout-pod-x", "checkout-pod-y"],
            "unhealthy_nodes": [],
        }
    }

    result = await correlator.execute(
        investigation_type=InvestigationType.CLUSTER_RESOURCE_ALERT,
        findings_by_domain=findings,
    )

    assert result.confidence == ConfidenceLevel.HIGH
    assert result.cross_validated is True
    assert "2 pod(s) terminated due to OOMKilled" in result.root_cause_summary
    assert result.validated_by_specialists == ["kubernetes"]
