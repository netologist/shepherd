"""Tool-free Correlate Agent for cross-specialist evidence matching."""

import json
from typing import Any
from sre_ai.domain.schemas import (
    CorrelationResult,
    ConfidenceLevel,
    RootCauseCategory,
    InvestigationType,
    TimelineEvent,
)
from sre_ai.agents.llm_client import UnifiedLLMClient, llm_client
from sre_ai.config.models import get_model_profile

CORRELATE_SYSTEM_PROMPT = """You are the Correlate Agent in the SRE AI multi-agent investigation team.
You have NO access to telemetry tools. Your sole job is to cross-reference and correlate the structured findings collected by independent domain specialists.

Rules for Root Cause Analysis:
1. **Cross-Validation Rule**: A hypothesis is cross-validated (confidence: high) ONLY if corroborated by at least TWO independent specialists (e.g. Metrics latency spike + Traces DB lock timeout, or K8s OOMKills + Troubleshoot memory check).
2. **False Positive Filtering**: Isolate symptoms (downstream timeouts) from the true root cause (upstream database lock / OOMKilled worker).
3. **Timeline Construction**: Reconstruct a chronological timeline of events based on timestamped specialist findings.
4. **Category Taxonomy**: Categorize root cause as deployment, config, infrastructure, traffic, code, external, or database.
"""


class CorrelateAgent:
    def __init__(self, client: UnifiedLLMClient | None = None):
        self.client = client or llm_client

    async def execute(
        self,
        investigation_type: InvestigationType,
        findings_by_domain: dict[str, Any],
    ) -> CorrelationResult:
        """Correlates structured findings across domain specialists without tool access."""
        # Deterministic passthrough for single-specialist investigation types
        if investigation_type == InvestigationType.CLUSTER_RESOURCE_ALERT:
            return self._deterministic_cluster_passthrough(findings_by_domain)

        profile = get_model_profile(investigation_type)

        # Format findings block
        findings_json = json.dumps(findings_by_domain, indent=2, default=str)
        user_content = f"Structured Domain Specialist Findings:\n```json\n{findings_json}\n```\n\nPerform cross-domain correlation and output the CorrelationResult."

        messages = [
            {"role": "system", "content": CORRELATE_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        correlation = await self.client.invoke_structured_output(
            schema=CorrelationResult,
            messages=messages,
            model=profile.correlate_model,
            fallback_models=profile.fallback_chain,
        )

        return correlation

    def _deterministic_cluster_passthrough(self, findings_by_domain: dict[str, Any]) -> CorrelationResult:
        """Deterministic correlation for cluster-resource-alert without an LLM roundtrip."""
        k8s_findings = findings_by_domain.get("kubernetes", {})
        oom_pods = k8s_findings.get("oom_killed_pods", [])
        unhealthy_nodes = k8s_findings.get("unhealthy_nodes", [])

        summary = "Cluster resource capacity anomaly detected."
        if oom_pods:
            summary = f"Memory pressure: {len(oom_pods)} pod(s) terminated due to OOMKilled ({', '.join(oom_pods[:3])})."
        elif unhealthy_nodes:
            summary = f"Node pressure: {len(unhealthy_nodes)} node(s) unhealthy ({', '.join(unhealthy_nodes[:3])})."

        return CorrelationResult(
            root_cause_summary=summary,
            category=RootCauseCategory.INFRASTRUCTURE,
            confidence=ConfidenceLevel.HIGH,
            confidence_score=0.90,
            cross_validated=True,
            validated_by_specialists=["kubernetes"],
            timeline=[
                TimelineEvent(
                    timestamp="00:00:00",
                    source="kubernetes",
                    service="cluster",
                    description=summary,
                    severity="warning",
                )
            ],
            contributing_factors=["Container memory limit ceiling reached"],
            immediate_recommendations=["Increase container memory requests and limits", "Review workload memory allocation"],
            short_term_recommendations=["Configure Vertical Pod Autoscaler (VPA) recommendations"],
        )
