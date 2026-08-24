"""Troubleshoot Specialist Agent."""

from sre_ai.agents.specialists.base import BaseSpecialist
from sre_ai.domain.schemas import TroubleshootFindings
from sre_ai.mcp.troubleshoot import create_troubleshoot_mcp_client

TROUBLESHOOT_SYSTEM_PROMPT = """You are the Troubleshoot Specialist in the SRE AI multi-agent investigation team.
Your responsibility is to review automated static pre-checks, incident declarations, and baseline infrastructure diagnostics.
- Analyze pre-fetched troubleshooting reports to avoid redundant API calls.
- Execute composite static infra checks (databases, Redis, Kafka, DNS) to identify underlying resource saturation.
- Cross-correlate static findings with incident onset times.
"""


class TroubleshootSpecialist(BaseSpecialist):
    def __init__(self, mcp_client=None):
        client = mcp_client or create_troubleshoot_mcp_client()
        super().__init__(
            domain="troubleshoot",
            mcp_client=client,
            findings_schema=TroubleshootFindings,
            system_prompt=TROUBLESHOOT_SYSTEM_PROMPT,
        )
