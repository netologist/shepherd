"""Gather Agent & Prefetch Node."""

import asyncio
import re
from typing import Any
from shepherd.domain.schemas import IncidentContext, InvestigationBrief, InvestigationType
from shepherd.mcp.troubleshoot import create_troubleshoot_mcp_client
from shepherd.agents.llm_client import UnifiedLLMClient, llm_client
from shepherd.config.models import get_model_profile

INCIDENT_REGEX = re.compile(r"(?i)\b(INC-\d+|INCIDENT-\d+)\b")
TROUBLESHOOT_REGEX = re.compile(r"(?i)\b(RCA-\d+|TROUBLESHOOT-\d+|TS-\d+)\b")
NAMESPACE_REGEX = re.compile(r"(?i)\b(?:namespace|ns)[:=\s]+([a-zA-Z0-9_-]+)\b")
SERVICE_REGEX = re.compile(r"(?i)\b(?:service|app|workload)[:=\s]+([a-zA-Z0-9_-]+)\b")


def extract_regex_context(raw_text: str) -> dict[str, Any]:
    """Scans user prompt with regex to extract incident and troubleshooting identifiers."""
    inc_match = INCIDENT_REGEX.search(raw_text)
    ts_match = TROUBLESHOOT_REGEX.search(raw_text)
    ns_match = NAMESPACE_REGEX.search(raw_text)
    svc_match = SERVICE_REGEX.search(raw_text)

    return {
        "incident_id": inc_match.group(1).upper() if inc_match else None,
        "troubleshoot_id": ts_match.group(1).upper() if ts_match else None,
        "namespace": ns_match.group(1) if ns_match else "prod",
        "service_name": svc_match.group(1) if svc_match else None,
    }


GATHER_SYSTEM_PROMPTS = {
    InvestigationType.INCIDENT_REVIEW: """You are the Gather Agent for Incident Review investigations.
Analyze the pre-fetched incident data and user report. Produce a structured InvestigationBrief detailing:
- The core problem statement
- Suspected domain specialists to fan out (metrics, traces, kubernetes, troubleshoot)
- Concrete focus services and explicit healthy services to skip
- Guiding priority questions for specialists
""",
    InvestigationType.ONCALL_ALERT: """You are the Gather Agent for On-Call Alert Triage.
Analyze the incoming alert payload and generate a focused InvestigationBrief prioritizing latency and error-rate anomalies.
""",
    InvestigationType.QA_SUPPORT: """You are the Gather Agent for SRE QA Support.
Extract the technical question context and determine which specialist data is required to answer the engineer's query.
""",
}


class GatherAgent:
    def __init__(self, client: UnifiedLLMClient | None = None):
        self.client = client or llm_client
        self.troubleshoot_mcp = create_troubleshoot_mcp_client()

    async def prefetch_data(self, incident_id: str | None, troubleshoot_id: str | None) -> dict[str, str]:
        """Pre-fetches targeted telemetry in parallel before running gather LLM."""
        prefetched: dict[str, str] = {}
        tasks = []
        task_keys = []

        if incident_id:
            tasks.append(self.troubleshoot_mcp.call_tool("investigate_incident", {"incident_id": incident_id}))
            task_keys.append("incident_summary")
            tasks.append(self.troubleshoot_mcp.call_tool("get_intelligent_troubleshooting", {"incident_id": incident_id}))
            task_keys.append("intelligent_troubleshooting")

        if troubleshoot_id:
            tasks.append(self.troubleshoot_mcp.call_tool("get_troubleshooting_detail", {"rca_id": troubleshoot_id}))
            task_keys.append("troubleshooting_detail")

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for key, res in zip(task_keys, results):
                if isinstance(res, str):
                    prefetched[key] = res

        return prefetched

    async def execute(
        self,
        raw_text: str,
        investigation_type: InvestigationType = InvestigationType.INCIDENT_REVIEW,
    ) -> tuple[IncidentContext, InvestigationBrief, dict[str, str]]:
        """Executes regex extraction, parallel prefetch, and structured brief generation."""
        extracted = extract_regex_context(raw_text)
        prefetched = await self.prefetch_data(extracted["incident_id"], extracted["troubleshoot_id"])

        profile = get_model_profile(investigation_type)
        sys_prompt = GATHER_SYSTEM_PROMPTS.get(investigation_type, GATHER_SYSTEM_PROMPTS[InvestigationType.INCIDENT_REVIEW])

        user_content = f"User Request / Alert Payload:\n{raw_text}\n"
        if prefetched:
            user_content += "\nPre-fetched Context:\n"
            for k, v in prefetched.items():
                user_content += f"\n### {k}\n{v}\n"

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content},
        ]

        brief = await self.client.invoke_structured_output(
            schema=InvestigationBrief,
            messages=messages,
            model=profile.gather_model,
            fallback_models=profile.fallback_chain,
        )

        # Override incident_id if extracted via regex
        if extracted["incident_id"] and brief.incident_id in ("UNKNOWN", "", None):
            brief.incident_id = extracted["incident_id"]

        context = IncidentContext(
            incident_id=extracted["incident_id"] or brief.incident_id,
            troubleshoot_id=extracted["troubleshoot_id"],
            service_name=extracted["service_name"],
            namespace=extracted["namespace"],
            raw_text=raw_text,
            has_slo_impact="slo" in raw_text.lower() or "cuj" in raw_text.lower(),
            has_multi_service_impact="cascade" in raw_text.lower() or "multiple" in raw_text.lower(),
        )

        return context, brief, prefetched
