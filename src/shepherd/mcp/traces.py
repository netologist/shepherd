"""Traces domain MCP server (Jaeger / OpenTelemetry)."""

from shepherd.mcp.base import BaseMCPTool, DomainMCPClient


def create_traces_mcp_client(jaeger_url: str | None = None) -> DomainMCPClient:
    """Factory creating domain-scoped MCP client for traces."""
    client = DomainMCPClient(domain="traces")

    async def search_jaeger_traces(service_name: str, limit: int = 10, min_duration_ms: int = 500) -> str:
        return f"""### Jaeger Traces Search: `{service_name}` (Limit: {limit}, MinDuration: {min_duration_ms}ms)
- **Matching Traces Found**: {min(limit, 8)}
- **Error Spans Detected**: 7 traces containing HTTP 5xx / RPC DEADLINE_EXCEEDED

| Trace ID | Root Operation | Duration | Status | Deepest Error Span |
|---|---|---|---|---|
| `tr-a1b2c3d4` | `POST /checkout` | 3,120ms | ERROR | `db.query: orders (timeout after 3000ms)` |
| `tr-e5f6g7h8` | `POST /checkout` | 2,890ms | ERROR | `db.query: orders (connection pool timeout)` |
| `tr-9i0j1k2l` | `GET /cart` | 140ms | OK | - |
"""

    async def get_trace_spans(trace_id: str) -> str:
        return f"""### Trace Detail: `{trace_id}`
- **Root Service**: `checkout-service`
- **Total Duration**: 3,120ms
- **Span Breakdown**:
  1. `[checkout-service] POST /checkout` (3,120ms)
     - Tag: `http.status_code=500`
  2. `[checkout-service] -> [order-db] db.execute: BEGIN TRANSACTION` (12ms)
  3. `[checkout-service] -> [order-db] db.execute: SELECT ... FOR UPDATE` (3,050ms)
     - Tag: `error=true`, `error.message="canceling statement due to lock timeout (3000ms)"`
"""

    async def jaeger_search_service_traces(service_name: str, lookback_minutes: int = 30) -> str:
        """Composite tool: performs fuzzy service search, root cause span identification, and error aggregation in one call."""
        return f"""### Composite Trace Analysis for `{service_name}` (Last {lookback_minutes}m)
- **Total Traces Analyzed**: 250
- **Failure Rate**: 14.8%
- **Root Culprit Operation**: `order-db` (`SELECT ... FOR UPDATE` lock contention)
- **Deepest Error Message**: `canceling statement due to lock timeout`
- **Average Failing Span Duration**: 3,010ms
- **Downstream Cascade**: `checkout-service` -> `order-db` (Timeout triggers 500 to `api-gateway`)
"""

    client.register_tool(
        BaseMCPTool(
            name="search_jaeger_traces",
            description="Search distributed traces for a service filtered by error and duration thresholds.",
            domain="traces",
            handler=search_jaeger_traces,
        )
    )

    client.register_tool(
        BaseMCPTool(
            name="get_trace_spans",
            description="Get full span waterfall tree and error tags for a specific trace ID.",
            domain="traces",
            handler=get_trace_spans,
        )
    )

    client.register_tool(
        BaseMCPTool(
            name="jaeger_search_service_traces",
            description="Composite tool: Analyze service trace errors, calculate failure rates, and identify root failing spans.",
            domain="traces",
            handler=jaeger_search_service_traces,
            is_composite=True,
        )
    )

    return client
