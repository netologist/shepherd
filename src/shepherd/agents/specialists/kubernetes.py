"""Kubernetes Specialist Agent."""

from shepherd.agents.specialists.base import BaseSpecialist
from shepherd.domain.schemas import KubernetesFindings
from shepherd.mcp.kubernetes import create_kubernetes_mcp_client

KUBERNETES_SYSTEM_PROMPT = """You are the Kubernetes Specialist in the SRE AI multi-agent investigation team.
Your responsibility is to inspect Kubernetes cluster, node, pod, and container health with read-only access.
- Prioritize composite tools like `diagnose_pod` and `get_workload_overview` to check OOMKilled events, restart loops, and deployment rollouts.
- Check for CrashLoopBackOff, memory limits, and warning events.
- Never suggest destructive mutations; focus on diagnosing workload anomalies.
"""


class KubernetesSpecialist(BaseSpecialist):
    def __init__(self, mcp_client=None):
        client = mcp_client or create_kubernetes_mcp_client()
        super().__init__(
            domain="kubernetes",
            mcp_client=client,
            findings_schema=KubernetesFindings,
            system_prompt=KUBERNETES_SYSTEM_PROMPT,
        )
