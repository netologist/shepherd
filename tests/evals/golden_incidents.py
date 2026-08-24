"""Golden SRE incident dataset for evaluation benchmarks."""

from typing import Any
from pydantic import BaseModel, Field
from shepherd.domain.schemas import RootCauseCategory, ConfidenceLevel, InvestigationType


class GoldenIncident(BaseModel):
    incident_id: str
    investigation_type: InvestigationType
    raw_prompt: str
    expected_category: RootCauseCategory
    expected_keywords: list[str]
    expected_cross_validated: bool
    min_confidence: ConfidenceLevel
    min_evidence_count: int = Field(default=2)
    sample_chat_query: str
    expected_chat_keywords: list[str]


GOLDEN_INCIDENTS: list[GoldenIncident] = [
    GoldenIncident(
        incident_id="INC-8088",
        investigation_type=InvestigationType.INCIDENT_REVIEW,
        raw_prompt=(
            "INC-8088: Alert triggered for service 'order-api' in namespace 'ecommerce-demo'. "
            "Pod restarts and 504 Gateway Timeouts reported. Please find the root cause."
        ),
        expected_category=RootCauseCategory.INFRASTRUCTURE,
        expected_keywords=["oom", "memory", "exit code 137", "order-api", "limit", "crash"],
        expected_cross_validated=True,
        min_confidence=ConfidenceLevel.HIGH,
        min_evidence_count=2,
        sample_chat_query="What was the exit code and memory limit that caused the crash?",
        expected_chat_keywords=["137", "oom", "memory"],
    ),
    GoldenIncident(
        incident_id="INC-1042",
        investigation_type=InvestigationType.INCIDENT_REVIEW,
        raw_prompt=(
            "INC-1042: Checkout service latency spiked to 3s and 5xx errors started appearing on order-db. "
            "Traffic surge of +35% detected."
        ),
        expected_category=RootCauseCategory.DATABASE,
        expected_keywords=["database", "pool", "connection", "lock", "starvation", "timeout"],
        expected_cross_validated=True,
        min_confidence=ConfidenceLevel.HIGH,
        min_evidence_count=2,
        sample_chat_query="Why did the connection pool starve on order-db?",
        expected_chat_keywords=["connection", "pool", "lock"],
    ),
    GoldenIncident(
        incident_id="INC-5021",
        investigation_type=InvestigationType.ONCALL_ALERT,
        raw_prompt=(
            "INC-5021: On-Call Alert - High latency on payment-gateway. "
            "P99 latency > 2500ms and downstream timeout to external banking provider."
        ),
        expected_category=RootCauseCategory.EXTERNAL,
        expected_keywords=["latency", "timeout", "payment", "downstream", "error"],
        expected_cross_validated=True,
        min_confidence=ConfidenceLevel.MEDIUM,
        min_evidence_count=2,
        sample_chat_query="Which downstream endpoint experienced latency spikes?",
        expected_chat_keywords=["latency", "downstream", "timeout"],
    ),
]
