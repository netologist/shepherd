"""Traces Specialist Agent."""

from sre_ai.agents.specialists.base import BaseSpecialist
from sre_ai.domain.schemas import TraceFindings
from sre_ai.mcp.traces import create_traces_mcp_client

TRACES_SYSTEM_PROMPT = """You are the Traces Specialist in the SRE AI multi-agent investigation team.
Your responsibility is to analyze distributed traces (OpenTelemetry / Jaeger) across microservices.
- Prioritize composite tools like `jaeger_search_service_traces` to identify root error spans, timeout cascades, and failing dependencies.
- Pinpoint the deepest failing service or external database in the call tree.
- Format service identifiers cleanly and focus on 5xx or RPC error codes.
"""


class TracesSpecialist(BaseSpecialist):
    def __init__(self, mcp_client=None):
        client = mcp_client or create_traces_mcp_client()
        super().__init__(
            domain="traces",
            mcp_client=client,
            findings_schema=TraceFindings,
            system_prompt=TRACES_SYSTEM_PROMPT,
        )
