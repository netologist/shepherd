"""Metrics Specialist Agent."""

from sre_ai.agents.specialists.base import BaseSpecialist
from sre_ai.domain.schemas import MetricsFindings
from sre_ai.mcp.metrics import create_metrics_mcp_client

METRICS_SYSTEM_PROMPT = """You are the Metrics Specialist in the SRE AI multi-agent investigation team.
Your responsibility is to analyze application performance metrics, Four Golden Signals (Latency, Traffic, Errors, Saturation), and PromQL queries.
- Prioritize composite tools like `get_service_golden_signals` and `application_perf_overview` to minimize tool overhead.
- Investigate error rate spikes, P99 latency anomalies, and throughput changes around the incident start time.
- Avoid calling tools outside your domain. Return concise, evidence-grounded findings.
"""


class MetricsSpecialist(BaseSpecialist):
    def __init__(self, mcp_client=None):
        client = mcp_client or create_metrics_mcp_client()
        super().__init__(
            domain="metrics",
            mcp_client=client,
            findings_schema=MetricsFindings,
            system_prompt=METRICS_SYSTEM_PROMPT,
        )
