"""Tests for specialist execution and registry resolution."""

import pytest
from sre_ai.domain.schemas import InvestigationBrief, MetricsFindings
from sre_ai.agents.specialists.registry import specialist_registry
from sre_ai.agents.specialists.metrics import MetricsSpecialist


def test_specialist_registry_alias_normalization():
    assert specialist_registry.normalize_name("k8s") == "kubernetes"
    assert specialist_registry.normalize_name("k8s-agent") == "kubernetes"
    assert specialist_registry.normalize_name("Kubernetes Specialist") == "kubernetes"
    assert specialist_registry.normalize_name("prom") == "metrics"
    assert specialist_registry.normalize_name("jaeger") == "traces"
    assert specialist_registry.normalize_name("troubleshooting") == "troubleshoot"


@pytest.mark.asyncio
async def test_specialist_two_phase_execution():
    specialist = MetricsSpecialist()
    brief = InvestigationBrief(
        incident_id="INC-1042",
        summary="High latency on checkout",
        suspected_domains=["metrics"],
        focus_areas=["checkout-service"],
    )

    findings = await specialist.execute(
        brief=brief,
        prefetched_data={"incident_id": "INC-1042"},
    )

    assert isinstance(findings, MetricsFindings)
    assert findings.service_name != ""
