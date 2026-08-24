"""Tests for domain-scoped MCP servers, composite tools, and guardrails."""

import pytest
from sre_ai.mcp.metrics import create_metrics_mcp_client
from sre_ai.mcp.kubernetes import create_kubernetes_mcp_client
from sre_ai.mcp.traces import create_traces_mcp_client
from sre_ai.mcp.troubleshoot import create_troubleshoot_mcp_client
from sre_ai.agents.guardrails import ToolGuardrailTracker


@pytest.mark.asyncio
async def test_metrics_composite_tools():
    client = create_metrics_mcp_client()
    tools = client.list_tools()
    assert any(t.name == "get_service_golden_signals" and t.is_composite for t in tools)
    assert any(t.name == "application_perf_overview" and t.is_composite for t in tools)

    output = await client.call_tool("get_service_golden_signals", {"service_name": "checkout", "namespace": "prod"})
    assert "Golden Signals for `prod/checkout`" in output
    assert "Latency (P99)" in output


@pytest.mark.asyncio
async def test_kubernetes_composite_tools():
    client = create_kubernetes_mcp_client()
    output = await client.call_tool("diagnose_pod", {"namespace": "prod", "pod_name": "checkout-pod-1"})
    assert "Diagnostic Report for Pod `prod/checkout-pod-1`" in output
    assert "OOMKilled" in output


@pytest.mark.asyncio
async def test_traces_composite_tools():
    client = create_traces_mcp_client()
    output = await client.call_tool("jaeger_search_service_traces", {"service_name": "checkout"})
    assert "Composite Trace Analysis for `checkout`" in output
    assert "Root Culprit Operation" in output


@pytest.mark.asyncio
async def test_troubleshoot_tools():
    client = create_troubleshoot_mcp_client()
    output = await client.call_tool("run_static_infra_checks", {"service_name": "checkout", "namespace": "prod"})
    assert "Static Infrastructure Check for `prod/checkout`" in output
    assert "Postgres DB (`order-db`)" in output


def test_tool_guardrail_duplicate_suppression():
    tracker = ToolGuardrailTracker(max_iterations=5)

    # First call permitted
    notice1 = tracker.check_and_record_call("diagnose_pod", {"pod_name": "pod-1"})
    assert notice1 is None
    assert tracker.current_iteration == 1

    # Exact duplicate suppressed
    notice2 = tracker.check_and_record_call("diagnose_pod", {"pod_name": "pod-1"})
    assert notice2 is not None
    assert "Duplicate call to 'diagnose_pod' with identical arguments was suppressed" in notice2
    # Iteration count should not increment on suppressed duplicate
    assert tracker.current_iteration == 1


def test_tool_guardrail_result_truncation():
    tracker = ToolGuardrailTracker(max_result_chars=100)
    large_payload = "A" * 500
    processed = tracker.process_tool_result(large_payload)

    assert len(processed) > 100
    assert "[TRUNCATED: Response exceeded 100 character limit]" in processed


def test_tool_guardrail_iteration_limit():
    tracker = ToolGuardrailTracker(max_iterations=2)
    tracker.check_and_record_call("tool_a", {"x": 1})
    tracker.check_and_record_call("tool_b", {"x": 2})

    # Third call hits max limit
    notice = tracker.check_and_record_call("tool_c", {"x": 3})
    assert notice is not None
    assert "Maximum tool iteration limit (2) reached" in notice
    assert tracker.is_exhausted is True
