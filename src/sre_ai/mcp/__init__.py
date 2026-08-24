"""Domain-scoped MCP tooling layer."""

from sre_ai.mcp.base import BaseMCPTool, DomainMCPClient, MCPToolDefinition
from sre_ai.mcp.metrics import create_metrics_mcp_client
from sre_ai.mcp.traces import create_traces_mcp_client
from sre_ai.mcp.kubernetes import create_kubernetes_mcp_client
from sre_ai.mcp.troubleshoot import create_troubleshoot_mcp_client

__all__ = [
    "BaseMCPTool",
    "DomainMCPClient",
    "MCPToolDefinition",
    "create_metrics_mcp_client",
    "create_traces_mcp_client",
    "create_kubernetes_mcp_client",
    "create_troubleshoot_mcp_client",
]
