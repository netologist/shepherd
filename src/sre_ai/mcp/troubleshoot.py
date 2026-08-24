"""Troubleshoot & pre-check domain MCP server."""

from sre_ai.mcp.base import BaseMCPTool, DomainMCPClient


def create_troubleshoot_mcp_client() -> DomainMCPClient:
    """Factory creating domain-scoped MCP client for incident pre-checks and static diagnostics."""
    client = DomainMCPClient(domain="troubleshoot")

    async def investigate_incident(incident_id: str) -> str:
        return f"""### Incident Summary: `{incident_id}`
- **Title**: High Latency & 5xx Spikes on Checkout Flow
- **Severity**: P1 - High
- **Declared At**: 14:25 UTC
- **Affected Services**: `checkout-service`, `payment-api`
- **Initial Description**: Customer checkout timeouts reported across web and mobile gateways.
"""

    async def get_intelligent_troubleshooting(incident_id: str) -> str:
        return f"""### Automated Pre-Check Overview for `{incident_id}`
- **Automated Checks Run**: 18
- **Failed Checks**: 2
  1. `db_connection_starvation`: checkout-db active pool connection > 95%
  2. `k8s_oom_detection`: 2 pods in namespace `prod` terminated with OOMKilled
- **Warning Checks**: 1
  1. `upstream_gateway_504`: nginx ingress returning 504 gateway timeout
- **Healthy Checks**: 15 (DNS, TLS, Redis, Kafka, NodeDisk, NodeCPU)
"""

    async def get_troubleshooting_detail(rca_id: str) -> str:
        return f"""### Troubleshooting Detail Report: `{rca_id}`
- **Target Component**: `checkout-service`
- **Suspect Root Cause**: Database lock contention causing connection pool exhaustion, resulting in thread starvation and memory ballooning.
- **Correlated Change**: No deployment within 60m; traffic increase observed (+35% spike).
"""

    async def run_static_infra_checks(service_name: str, namespace: str = "default") -> str:
        """Composite tool: runs static diagnostics across infrastructure dependencies."""
        return f"""### Static Infrastructure Check for `{namespace}/{service_name}`
- **Postgres DB (`order-db`)**: 
  - Status: CONNECTED, CPU: 42%, Active Connections: 98/100 (**CRITICAL**)
  - Deadlocks Detected: 0 | Lock Wait Time: 3,200ms (**HIGH**)
- **Redis Cluster**: CONNECTED, Hit Rate: 95%, Memory: 45% (HEALTHY)
- **Kafka Cluster**: In-sync replicas healthy, consumer lag: 120 msgs (HEALTHY)
- **DNS / CoreDNS**: Latency 1.2ms (HEALTHY)
"""

    client.register_tool(
        BaseMCPTool(
            name="investigate_incident",
            description="Fetch incident metadata, severity, affected services, and description by incident ID.",
            domain="troubleshoot",
            handler=investigate_incident,
        )
    )

    client.register_tool(
        BaseMCPTool(
            name="get_intelligent_troubleshooting",
            description="Fetch automated static pre-check results for an incident ID.",
            domain="troubleshoot",
            handler=get_intelligent_troubleshooting,
        )
    )

    client.register_tool(
        BaseMCPTool(
            name="get_troubleshooting_detail",
            description="Fetch detailed RCA report and diagnostic telemetry by troubleshooting report ID.",
            domain="troubleshoot",
            handler=get_troubleshooting_detail,
        )
    )

    client.register_tool(
        BaseMCPTool(
            name="run_static_infra_checks",
            description="Composite tool: Execute static health checks on databases, caches, queues, and DNS.",
            domain="troubleshoot",
            handler=run_static_infra_checks,
            is_composite=True,
        )
    )

    return client
