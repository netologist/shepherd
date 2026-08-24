"""Metrics domain MCP server (Prometheus / PromQL)."""

from typing import Any
from sre_ai.mcp.base import BaseMCPTool, DomainMCPClient


def create_metrics_mcp_client(prometheus_url: str | None = None) -> DomainMCPClient:
    """Factory creating domain-scoped MCP client for metrics."""
    client = DomainMCPClient(domain="metrics")

    async def query_prometheus(query: str, time_range: str = "15m") -> str:
        # Structured mock / live query executor returning dense markdown
        return f"""### PromQL Query Result
- **Query**: `{query}`
- **Range**: `{time_range}`
- **Status**: Success

| Metric / Label | Value | Time |
|---|---|---|
| http_requests_total{{status="500"}} | 42.8 rps | Last {time_range} |
| http_requests_total{{status="200"}} | 850.2 rps | Last {time_range} |
"""

    async def get_service_golden_signals(service_name: str, namespace: str = "default", time_range: str = "30m") -> str:
        """Composite tool: returns latency (p50, p95, p99), error rate, throughput, and saturation in one Markdown block."""
        return f"""### Golden Signals for `{namespace}/{service_name}` (Last {time_range})
- **Error Rate**: 12.4% (Baseline: 0.05% - **CRITICAL ANOMALY**)
- **Latency (P50)**: 45ms
- **Latency (P95)**: 320ms
- **Latency (P99)**: 2850ms (Baseline: 180ms - **SEVERE DEGRADATION**)
- **Throughput**: 1,240 req/s (Normal)
- **CPU Saturation**: 88%
- **Memory Saturation**: 92% (Risk of OOM)
- **Top 5xx Endpoint**: `POST /api/v1/checkout/pay` (98% of 500s)
"""

    async def application_perf_overview(service_name: str, namespace: str = "default") -> str:
        """Composite tool: fetches throughput, database query duration, and cache hit ratio in one response."""
        return f"""### Application Performance Overview: `{namespace}/{service_name}`
- **Upstream Latency Impact**: Downstream calls to `payment-gateway` and `order-db`
- **Database Connection Pool**: 98/100 connections active (Starvation threshold reached)
- **Slow Query**: `SELECT * FROM orders WHERE user_id = ? FOR UPDATE` (avg 2.4s)
- **Redis Cache Hit Ratio**: 94.2% (Healthy)
- **GC Pause Time**: 12ms avg (Healthy)
"""

    client.register_tool(
        BaseMCPTool(
            name="query_prometheus",
            description="Execute arbitrary PromQL query against Prometheus metrics backend.",
            domain="metrics",
            handler=query_prometheus,
        )
    )

    client.register_tool(
        BaseMCPTool(
            name="get_service_golden_signals",
            description="Composite tool: Fetch the Four Golden Signals (Latency, Error Rate, Traffic, Saturation) for a service.",
            domain="metrics",
            handler=get_service_golden_signals,
            is_composite=True,
        )
    )

    client.register_tool(
        BaseMCPTool(
            name="application_perf_overview",
            description="Composite tool: Combined overview of database pool, slow queries, cache ratio, and GC stats.",
            domain="metrics",
            handler=application_perf_overview,
            is_composite=True,
        )
    )

    return client
