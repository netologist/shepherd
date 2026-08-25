"""Post-Investigation Chat Agent with live MCP tool access."""

import json
import logging
from typing import Any
from shepherd.domain.schemas import FinalReport, IncidentContext
from shepherd.agents.llm_client import UnifiedLLMClient, llm_client
from shepherd.mcp.metrics import create_metrics_mcp_client
from shepherd.mcp.traces import create_traces_mcp_client
from shepherd.mcp.kubernetes import create_kubernetes_mcp_client
from shepherd.mcp.troubleshoot import create_troubleshoot_mcp_client

logger = logging.getLogger(__name__)

# Maximum tool iterations per chat turn to prevent runaway loops
_MAX_TOOL_ITERATIONS = 8

CHAT_SYSTEM_PROMPT = """You are the SRE AI Post-Investigation Assistant.
You are assisting an on-call SRE engineer who is reviewing the completed incident investigation report.
- You have full access to the investigation report, findings, and live SRE telemetry MCP tools.
- You can explain root causes, verify hypotheses with live queries, or run targeted diagnostics on demand.
- Keep responses concise, evidence-based, and actionable.
- When you call a tool, interpret its output and synthesize a final answer — do not relay raw tool output.
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
        """Processes a chat turn with conversational history and a bounded tool-use loop.

        Tool calls are executed iteratively until the model produces a final text response
        or the iteration cap is reached — preventing runaway tool chains.
        """
        state_summary = f"""## Completed Investigation State
- Incident ID: {context.incident_id if context else 'UNKNOWN'}
- Primary Root Cause: {final_report.primary_root_cause if final_report else 'In Progress'}
- Confidence: {final_report.confidence.value if final_report else 'unknown'}
- Category: {final_report.category.value if final_report else 'unknown'}
- Specialists Involved: {list(findings_by_domain.keys())}
"""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": f"{CHAT_SYSTEM_PROMPT}\n\n{state_summary}"}
        ]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": user_message})

        tools = self._get_all_tools()

        # Bounded tool-use loop: continue while the model requests tools and
        # iterations remain. Each tool call result is fed back as a user turn
        # so the model can chain or synthesize.
        for iteration in range(_MAX_TOOL_ITERATIONS):
            response = await self.client.invoke_chat(
                messages=messages,
                model=model,
                tools=tools,
            )

            if not response.tool_calls:
                # Model produced a final text response — done.
                return response.content

            # Execute all tool calls from this iteration in parallel.
            import asyncio as _asyncio
            tool_results = await _asyncio.gather(*[
                self._execute_tool(tc["name"], tc.get("arguments", {}))
                for tc in response.tool_calls
            ])

            # Append the assistant's tool-calling turn and results to history.
            tool_call_summary = "; ".join(
                tc["name"] + "(" + json.dumps(tc.get("arguments", {})) + ")"
                for tc in response.tool_calls
            )
            messages.append({
                "role": "assistant",
                "content": response.content or f"Calling tools: {tool_call_summary}",
            })

            result_block = "\n\n".join(
                f"**{tc['name']} result:**\n{res}"
                for tc, res in zip(response.tool_calls, tool_results)
            )
            messages.append({"role": "user", "content": result_block})

        # Iteration cap reached — ask model to synthesize with collected evidence.
        logger.warning("Chat tool loop hit iteration cap (%d), requesting synthesis", _MAX_TOOL_ITERATIONS)
        messages.append({
            "role": "user",
            "content": "You have reached the tool call limit. Synthesize your final answer for the engineer using all evidence collected above.",
        })
        final = await self.client.invoke_chat(messages=messages, model=model)
        return final.content
