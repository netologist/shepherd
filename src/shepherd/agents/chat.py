"""Post-Investigation Chat Agent with live MCP tool access."""

import json
from typing import Any
from shepherd.domain.schemas import FinalReport, IncidentContext
from shepherd.agents.llm_client import UnifiedLLMClient, llm_client
from shepherd.mcp.metrics import create_metrics_mcp_client
from shepherd.mcp.traces import create_traces_mcp_client
from shepherd.mcp.kubernetes import create_kubernetes_mcp_client
from shepherd.mcp.troubleshoot import create_troubleshoot_mcp_client

CHAT_SYSTEM_PROMPT = """You are the SRE AI Post-Investigation Assistant.
You are assisting an on-call SRE engineer who is reviewing the completed incident investigation report.
- You have full access to the investigation report, findings, and live SRE telemetry MCP tools.
- You can explain root causes, verify hypotheses with live queries, or run targeted diagnostics on demand.
- Keep responses concise, evidence-based, and actionable.
"""


class PostInvestigationChatAgent:
    def __init__(self, client: UnifiedLLMClient | None = None):
        self.client = client or llm_client
        self.mcp_clients = {
            "metrics": create_metrics_mcp_client(),
            "traces": create_traces_mcp_client(),
            "kubernetes": create_kubernetes_mcp_client(),
            "troubleshoot": create_troubleshoot_mcp_client(),
        }

    def _get_all_tools(self) -> list[dict[str, Any]]:
        tools = []
        for client in self.mcp_clients.values():
            for t in client.list_tools():
                tools.append({
                    "name": t.name,
                    "description": f"[{t.domain}] {t.description}",
                    "parameters": t.parameters,
                })
        return tools

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> str:
        for client in self.mcp_clients.values():
            tool = client.get_tool(name)
            if tool:
                return await tool.execute(**args)
        return f"Error: Tool '{name}' not found in any domain."

    async def chat(
        self,
        user_message: str,
        final_report: FinalReport | None,
        context: IncidentContext | None,
        findings_by_domain: dict[str, Any],
        conversation_history: list[dict[str, str]] | None = None,
        model: str = "anthropic/claude-3-7-sonnet",
    ) -> str:
        """Processes a chat turn with conversational history and optional live tool loop."""
        state_summary = f"""## Completed Investigation State
- Incident ID: {context.incident_id if context else 'UNKNOWN'}
- Primary Root Cause: {final_report.primary_root_cause if final_report else 'In Progress'}
- Confidence: {final_report.confidence.value if final_report else 'unknown'}
- Category: {final_report.category.value if final_report else 'unknown'}
- Specialists Involved: {list(findings_by_domain.keys())}
"""
        messages = [{"role": "system", "content": f"{CHAT_SYSTEM_PROMPT}\n\n{state_summary}"}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        tools = self._get_all_tools()
        # Single-turn tool execution loop
        response = await self.client.invoke_chat(
            messages=messages,
            model=model,
            tools=tools,
        )

        if response.tool_calls:
            # Handle tool calls
            tool_results = []
            for tc in response.tool_calls:
                res = await self._execute_tool(tc["name"], tc.get("arguments", {}))
                tool_results.append(f"Result for {tc['name']}:\n{res}")

            messages.append({"role": "assistant", "content": response.content or "Executing telemetry verification..."})
            messages.append({"role": "user", "content": "\n\n".join(tool_results) + "\n\nSynthesize your final answer for the engineer."})

            followup = await self.client.invoke_chat(messages=messages, model=model)
            return followup.content

        return response.content
