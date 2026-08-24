"""Domain-scoped MCP tooling layer."""

from shepherd.mcp.base import BaseMCPTool, DomainMCPClient, MCPToolDefinition
from shepherd.mcp.metrics import create_metrics_mcp_client
from shepherd.mcp.traces import create_traces_mcp_client
from shepherd.mcp.kubernetes import create_kubernetes_mcp_client
from shepherd.mcp.troubleshoot import create_troubleshoot_mcp_client

__all__ = [
    "BaseMCPTool",
    "DomainMCPClient",
    "MCPToolDefinition",
    "create_metrics_mcp_client",
    "create_traces_mcp_client",
    "create_kubernetes_mcp_client",
    "create_troubleshoot_mcp_client",
]
