"""Tests for safe coercion validators and domain schemas."""

from sre_ai.domain.coercion import (
    safe_float_coerce,
    safe_int_coerce,
    safe_str_list_coerce,
)
from sre_ai.domain.schemas import (
    MetricsFindings,
    TraceFindings,
    KubernetesFindings,
    TroubleshootFindings,
    CorrelationResult,
    ConfidenceLevel,
    RootCauseCategory,
    FinalReport,
)


def test_safe_float_coerce():
    assert safe_float_coerce(42.5) == 42.5
    assert safe_float_coerce(10) == 10.0
    assert safe_float_coerce("25.4%") == 25.4
    assert safe_float_coerce("<UNKNOWN>") == 0.0
    assert safe_float_coerce("N/A") == 0.0
    assert safe_float_coerce(None) == 0.0
    assert safe_float_coerce("approx 120.5 ms") == 120.5


def test_safe_int_coerce():
    assert safe_int_coerce(5) == 5
    assert safe_int_coerce("42") == 42
    assert safe_int_coerce("N/A") == 0
    assert safe_int_coerce(None) == 0


def test_safe_str_list_coerce():
    assert safe_str_list_coerce(["a", "b"]) == ["a", "b"]
    assert safe_str_list_coerce("a, b, c") == ["a", "b", "c"]
    assert safe_str_list_coerce("single-item") == ["single-item"]
    assert safe_str_list_coerce(None) == []
    assert safe_str_list_coerce("") == []


def test_metrics_findings_coercion():
    findings = MetricsFindings(
        service_name="checkout-service",
        error_rate_pct="12.5%",  # type: ignore
        p99_latency_ms="2850ms",  # type: ignore
        throughput_rps="N/A",  # type: ignore
        anomalous_metrics="cpu, memory",  # type: ignore
    )
    assert findings.error_rate_pct == 12.5
    assert findings.p99_latency_ms == 2850.0
    assert findings.throughput_rps == 0.0
    assert findings.anomalous_metrics == ["cpu", "memory"]


def test_kubernetes_findings_coercion():
    findings = KubernetesFindings(
        cluster="prod-eu",
        namespace="checkout",
        oom_killed_pods="pod-a, pod-b",  # type: ignore
        restarting_pods=None,  # type: ignore
    )
    assert findings.oom_killed_pods == ["pod-a", "pod-b"]
    assert findings.restarting_pods == []


def test_correlation_result_schema():
    corr = CorrelationResult(
        root_cause_summary="DB pool exhaustion",
        category=RootCauseCategory.DATABASE,
        confidence=ConfidenceLevel.HIGH,
        confidence_score="0.95",  # type: ignore
        cross_validated=True,
        validated_by_specialists="metrics, traces",  # type: ignore
    )
    assert corr.confidence_score == 0.95
    assert corr.validated_by_specialists == ["metrics", "traces"]
    assert corr.cross_validated is True
