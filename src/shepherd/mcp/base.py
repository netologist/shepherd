"""Base abstractions for Domain-Scoped MCP tools and clients."""

from typing import Any, Callable, Awaitable
from pydantic import BaseModel, Field
import json
import inspect


class MCPToolDefinition(BaseModel):
    name: str = Field(description="Unique tool name")
    description: str = Field(description="Operational summary of what the tool does")
    parameters: dict[str, Any] = Field(description="JSON schema for parameters")
    domain: str = Field(description="Domain boundary (metrics, traces, kubernetes, troubleshoot)")
    is_composite: bool = Field(default=False, description="True if composite tool aggregating multiple queries")


class BaseMCPTool:
    """Standard wrapper for an MCP tool returning dense markdown."""

    def __init__(
        self,
        name: str,
        description: str,
        domain: str,
        handler: Callable[..., Awaitable[str] | str],
        parameters_schema: dict[str, Any] | None = None,
        is_composite: bool = False,
    ):
        self.name = name
        self.description = description
        self.domain = domain
        self.handler = handler
        self.is_composite = is_composite
        self.parameters_schema = parameters_schema or self._infer_schema()

    def _infer_schema(self) -> dict[str, Any]:
        sig = inspect.signature(self.handler)
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            param_type = "string"
            if param.annotation is int:
                param_type = "integer"
            elif param.annotation is float:
                param_type = "number"
            elif param.annotation is bool:
                param_type = "boolean"
            elif param.annotation is list:
                param_type = "array"

            properties[param_name] = {"type": param_type}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    async def execute(self, **kwargs) -> str:
        """Execute the tool handler and return dense markdown string."""
        if inspect.iscoroutinefunction(self.handler):
            return await self.handler(**kwargs)
        return self.handler(**kwargs)

    def to_tool_def(self) -> MCPToolDefinition:
        return MCPToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema,
            domain=self.domain,
            is_composite=self.is_composite,
        )


class DomainMCPClient:
    """Client for a specific domain's MCP server containing only scoped tools."""

    def __init__(self, domain: str):
        self.domain = domain
        self._tools: dict[str, BaseMCPTool] = {}

    def register_tool(self, tool: BaseMCPTool) -> None:
        self._tools[tool.name] = tool

    def list_tools(self) -> list[MCPToolDefinition]:
        return [tool.to_tool_def() for tool in self._tools.values()]

    def get_tool(self, name: str) -> BaseMCPTool | None:
        return self._tools.get(name)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found in domain '{self.domain}'."
        try:
            return await tool.execute(**arguments)
        except Exception as e:
            return f"Error executing '{name}' in domain '{self.domain}': {str(e)}"
