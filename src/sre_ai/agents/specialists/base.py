"""Base two-phase specialist execution framework."""

import logging
from typing import Any, Type, TypeVar
from pydantic import BaseModel

from sre_ai.domain.schemas import InvestigationBrief
from sre_ai.mcp.base import DomainMCPClient
from sre_ai.agents.guardrails import ToolGuardrailTracker
from sre_ai.agents.llm_client import UnifiedLLMClient, llm_client

logger = logging.getLogger(__name__)

TFindings = TypeVar("TFindings", bound=BaseModel)


class BaseSpecialist:
    """Standard implementation of a domain specialist following the two-phase execution model."""

    def __init__(
        self,
        domain: str,
        mcp_client: DomainMCPClient,
        findings_schema: Type[TFindings],
        system_prompt: str,
        client: UnifiedLLMClient | None = None,
        max_iterations: int = 15,
    ):
        self.domain = domain
        self.mcp_client = mcp_client
        self.findings_schema = findings_schema
        self.system_prompt = system_prompt
        self.client = client or llm_client
        self.max_iterations = max_iterations

    async def execute(
        self,
        brief: InvestigationBrief,
        prefetched_data: dict[str, Any] | None = None,
        additional_instructions: str | None = None,
        model: str = "gemini/gemini-2.5-pro",
        fallback_models: list[str] | None = None,
    ) -> TFindings:
        """Runs Phase 1 (Tool Loop) followed by Phase 2 (Structured Findings Extraction)."""
        tracker = ToolGuardrailTracker(max_iterations=self.max_iterations)
        tools_def = [t.parameters for t in self.mcp_client.list_tools()]
        raw_tools = [{"name": t.name, "description": t.description, "parameters": t.parameters} for t in self.mcp_client.list_tools()]

        # Construct initial messages
        context_block = f"""## Investigation Brief
- Incident ID: {brief.incident_id}
- Summary: {brief.summary}
- Suspected Domains: {', '.join(brief.suspected_domains)}
- Focus Areas: {', '.join(brief.focus_areas)}
- Excluded Areas: {', '.join(brief.excluded_areas)}
- Priority Questions: {', '.join(brief.priority_questions)}
"""
        if prefetched_data:
            context_block += f"\n## Prefetched Data\n```json\n{prefetched_data}\n```\n(Note: Do not call tools to re-fetch this data)"

        if additional_instructions:
            context_block += f"\n## Targeted Deep-Dive Instructions\n{additional_instructions}"

        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"{context_block}\n\nPlease start your investigation in the '{self.domain}' domain."},
        ]

        # ── Phase 1: Tool-Use Loop ─────────────────────────────────────────
        iteration = 0
        while iteration < self.max_iterations and not tracker.is_exhausted and not tracker.budget_exceeded:
            iteration += 1
            response = await self.client.invoke_chat(
                messages=messages,
                model=model,
                fallback_models=fallback_models,
                tools=raw_tools,
            )

            # Record assistant turn
            messages.append({"role": "assistant", "content": response.content or ""})

            # If no tool calls requested, the LLM has finished its investigation loop
            if not response.tool_calls:
                break

            # Execute tool calls
            for tc in response.tool_calls:
                t_name = tc.get("name", "")
                t_args = tc.get("arguments", {})

                guard_notice = tracker.check_and_record_call(t_name, t_args)
                if guard_notice:
                    messages.append({"role": "user", "content": f"Tool '{t_name}' Notice: {guard_notice}"})
                    continue

                tool_output = await self.mcp_client.call_tool(t_name, t_args)
                processed_output = tracker.process_tool_result(tool_output)

                messages.append({
                    "role": "user",
                    "content": f"Tool '{t_name}' result:\n{processed_output}",
                })

        # ── Phase 2: Structured Findings Extraction ─────────────────────────
        # Tool-free LLM invocation converting accumulated investigation dialogue into typed Pydantic findings
        extraction_messages = list(messages)
        extraction_messages.append({
            "role": "user",
            "content": (
                "Based on the investigation history above, extract your definitive domain findings into the structured schema. "
                "Do not make any further tool calls."
            ),
        })

        try:
            findings = await self.client.invoke_structured_output(
                schema=self.findings_schema,
                messages=extraction_messages,
                model=model,
                fallback_models=fallback_models,
            )
            return findings
        except Exception as e:
            logger.error("Structured findings extraction failed for domain %s: %s", self.domain, e)
            # Safe fallback default finding
            return self.client._build_default_schema_instance(self.findings_schema, extraction_messages)
