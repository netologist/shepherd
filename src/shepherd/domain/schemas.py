"""Domain schemas and typed models for SRE AI multi-agent investigation."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator

from shepherd.domain.coercion import (
    safe_float_coerce,
    safe_int_coerce,
    safe_str_list_coerce,
)


class InvestigationType(str, Enum):
    INCIDENT_REVIEW = "incident-review"
    ONCALL_ALERT = "oncall-alert-analyzer"
    QA_SUPPORT = "qa-support"
    CLUSTER_RESOURCE_ALERT = "cluster-resource-alert"


class RootCauseCategory(str, Enum):
    DEPLOYMENT = "deployment"
    CONFIG = "config"
    INFRASTRUCTURE = "infrastructure"
    TRAFFIC = "traffic"
    CODE = "code"
    EXTERNAL = "external"
    DATABASE = "database"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TimelineEvent(BaseModel):
    timestamp: str = Field(description="ISO timestamp or relative time (e.g. 14:32:00)")
    source: str = Field(description="Originating specialist or telemetry source (e.g. metrics, traces, k8s)")
    service: str = Field(description="Affected service or component name")
    description: str = Field(description="Concise description of the anomaly or state change")
    severity: str = Field(default="info", description="Severity: info, warning, error, critical")


class IncidentContext(BaseModel):
    incident_id: str | None = Field(default=None, description="Incident ticket ID (e.g. INC-1234)")
    troubleshoot_id: str | None = Field(default=None, description="Pre-check / RCA report ID")
    service_name: str | None = Field(default=None, description="Primary suspect service name")
    namespace: str | None = Field(default=None, description="Kubernetes namespace")
    cluster: str | None = Field(default=None, description="Kubernetes cluster name")
    start_time: str | None = Field(default=None, description="Incident onset timestamp")
    raw_text: str = Field(default="", description="Original user prompt or alert payload")
    has_slo_impact: bool = Field(default=False, description="Flag indicating CUJ / SLO degradation")
    has_multi_service_impact: bool = Field(default=False, description="Flag indicating cascading multi-service impact")


class InvestigationBrief(BaseModel):
    incident_id: str = Field(default="UNKNOWN", description="Target incident ID")
    summary: str = Field(description="Incident overview and problem statement")
    suspected_domains: list[str] = Field(default_factory=list, description="Domains with high probability of anomalies")
    focus_areas: list[str] = Field(default_factory=list, description="Specific services or metrics to investigate")
    excluded_areas: list[str] = Field(default_factory=list, description="Components confirmed healthy to skip")
    priority_questions: list[str] = Field(default_factory=list, description="Guiding questions for specialists")

    @field_validator("suspected_domains", "focus_areas", "excluded_areas", "priority_questions", mode="before")
    @classmethod
    def coerce_lists(cls, v: Any) -> list[str]:
        return safe_str_list_coerce(v)


class MetricsFindings(BaseModel):
    service_name: str = Field(default="unknown", description="Target service analyzed")
    error_rate_pct: float = Field(default=0.0, description="Observed error rate percentage")
    p99_latency_ms: float = Field(default=0.0, description="P99 latency in milliseconds")
    throughput_rps: float = Field(default=0.0, description="Throughput in requests per second")
    anomalous_metrics: list[str] = Field(default_factory=list, description="Metrics exhibiting deviations")
    evidence_urls: list[str] = Field(default_factory=list, description="Grafana panel URLs or PromQL queries")
    summary: str = Field(default="", description="Executive domain summary")

    @field_validator("error_rate_pct", "p99_latency_ms", "throughput_rps", mode="before")
    @classmethod
    def coerce_floats(cls, v: Any) -> float:
        return safe_float_coerce(v)

    @field_validator("anomalous_metrics", "evidence_urls", mode="before")
    @classmethod
    def coerce_lists(cls, v: Any) -> list[str]:
        return safe_str_list_coerce(v)


class TraceFindings(BaseModel):
    service_name: str = Field(default="unknown", description="Service inspected in traces")
    failing_spans: list[str] = Field(default_factory=list, description="Specific failing span operations")
    root_span_service: str = Field(default="", description="Deepest failing dependency in the call tree")
    root_error_message: str = Field(default="", description="Exception or error message captured in spans")
    avg_duration_ms: float = Field(default=0.0, description="Average span duration in ms")
    error_rate_pct: float = Field(default=0.0, description="Percentage of traces with errors")
    summary: str = Field(default="", description="Trace analysis summary")

    @field_validator("avg_duration_ms", "error_rate_pct", mode="before")
    @classmethod
    def coerce_floats(cls, v: Any) -> float:
        return safe_float_coerce(v)

    @field_validator("failing_spans", mode="before")
    @classmethod
    def coerce_lists(cls, v: Any) -> list[str]:
        return safe_str_list_coerce(v)


class KubernetesFindings(BaseModel):
    cluster: str = Field(default="default", description="Cluster name")
    namespace: str = Field(default="default", description="Namespace analyzed")
    oom_killed_pods: list[str] = Field(default_factory=list, description="Pods terminated due to OOMKilled")
    restarting_pods: list[str] = Field(default_factory=list, description="Pods with CrashLoopBackOff or high restart counts")
    unhealthy_nodes: list[str] = Field(default_factory=list, description="Nodes with MemoryPressure, DiskPressure, or NotReady")
    warning_events: list[str] = Field(default_factory=list, description="Critical Kubernetes warning events")
    deployment_rollouts: list[str] = Field(default_factory=list, description="Recent deployments or config changes")
    summary: str = Field(default="", description="Kubernetes domain summary")

    @field_validator("oom_killed_pods", "restarting_pods", "unhealthy_nodes", "warning_events", "deployment_rollouts", mode="before")
    @classmethod
    def coerce_lists(cls, v: Any) -> list[str]:
        return safe_str_list_coerce(v)


class TroubleshootFindings(BaseModel):
    report_id: str = Field(default="", description="Troubleshooting report ID")
    static_checks_run: int = Field(default=0, description="Total automated static checks executed")
    failed_checks: list[str] = Field(default_factory=list, description="Failed pre-checks")
    warning_checks: list[str] = Field(default_factory=list, description="Warning-level pre-checks")
    suspect_infrastructure: list[str] = Field(default_factory=list, description="Identified suspect infra (DB, Redis, Network)")
    summary: str = Field(default="", description="Pre-check analysis summary")

    @field_validator("static_checks_run", mode="before")
    @classmethod
    def coerce_ints(cls, v: Any) -> int:
        return safe_int_coerce(v)

    @field_validator("failed_checks", "warning_checks", "suspect_infrastructure", mode="before")
    @classmethod
    def coerce_lists(cls, v: Any) -> list[str]:
        return safe_str_list_coerce(v)


class CUJFindings(BaseModel):
    critical_user_journey: str = Field(default="", description="CUJ name (e.g. MakePayment, SearchCatalog)")
    degraded_slos: list[str] = Field(default_factory=list, description="SLOs currently breaching error budget")
    root_culprit_service: str = Field(default="", description="Root bottleneck service in the user journey")
    affected_downstream: list[str] = Field(default_factory=list, description="Downstream services impacted")
    summary: str = Field(default="", description="CUJ & SLO impact summary")

    @field_validator("degraded_slos", "affected_downstream", mode="before")
    @classmethod
    def coerce_lists(cls, v: Any) -> list[str]:
        return safe_str_list_coerce(v)


class CorrelationResult(BaseModel):
    root_cause_summary: str = Field(description="Synthesized root cause explanation")
    category: RootCauseCategory = Field(default=RootCauseCategory.UNKNOWN, description="Root cause category taxonomy")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.LOW, description="RCA confidence level: high, medium, low")
    confidence_score: float = Field(default=0.0, description="Numeric confidence score between 0.0 and 1.0")
    cross_validated: bool = Field(default=False, description="True if confirmed by at least 2 independent specialists")
    validated_by_specialists: list[str] = Field(default_factory=list, description="List of specialists corroborating the RCA")
    timeline: list[TimelineEvent] = Field(default_factory=list, description="Chronological event reconstruction")
    contributing_factors: list[str] = Field(default_factory=list, description="Secondary factors that compounded the incident")
    immediate_recommendations: list[str] = Field(default_factory=list, description="Immediate mitigation steps")
    short_term_recommendations: list[str] = Field(default_factory=list, description="Permanent fixes and preventative tasks")

    @field_validator("confidence_score", mode="before")
    @classmethod
    def coerce_score(cls, v: Any) -> float:
        return safe_float_coerce(v)

    @field_validator("validated_by_specialists", "contributing_factors", "immediate_recommendations", "short_term_recommendations", mode="before")
    @classmethod
    def coerce_lists(cls, v: Any) -> list[str]:
        return safe_str_list_coerce(v)


class DeepDiveTask(BaseModel):
    specialist: str = Field(description="Target specialist key: metrics, traces, kubernetes, troubleshoot, cuj")
    question: str = Field(description="Targeted question to investigate")
    target_service: str | None = Field(default=None, description="Optional target service to focus on")
    time_window: str | None = Field(default=None, description="Optional specific time window (e.g. 14:30-14:45)")


class RootCauseHypothesis(BaseModel):
    title: str = Field(description="Hypothesis title")
    description: str = Field(description="Detailed explanation of the failure mechanism")
    category: RootCauseCategory = Field(default=RootCauseCategory.UNKNOWN)
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    evidence: list[str] = Field(default_factory=list, description="Evidence references backing this hypothesis")


class FinalReport(BaseModel):
    investigation_id: str = Field(description="Unique investigation ID")
    incident_id: str = Field(default="UNKNOWN", description="Incident ID investigated")
    investigation_type: InvestigationType = Field(default=InvestigationType.INCIDENT_REVIEW)
    primary_root_cause: str = Field(description="Definitive primary root cause statement")
    category: RootCauseCategory = Field(default=RootCauseCategory.UNKNOWN)
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM)
    cross_validated: bool = Field(default=False)
    root_cause_hypotheses: list[RootCauseHypothesis] = Field(default_factory=list)
    evidence_chain: list[str] = Field(default_factory=list, description="Detailed evidence chain from specialists")
    timeline: list[TimelineEvent] = Field(default_factory=list, description="Reconstructed incident timeline")
    impact_analysis: str = Field(description="Affected user flows, error rates, and blast radius")
    contributing_factors: list[str] = Field(default_factory=list)
    immediate_recommendations: list[str] = Field(default_factory=list)
    short_term_recommendations: list[str] = Field(default_factory=list)
    deep_dive_count: int = Field(default=0, description="Number of iterative deep-dive loops executed")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FeedbackReview(BaseModel):
    investigation_id: str = Field(description="Target investigation ID")
    rating: int = Field(ge=1, le=5, description="1 to 5 star rating")
    comment: str | None = Field(default=None, description="Optional user commentary")
    reviewer: str | None = Field(default=None, description="Reviewer email or handle")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
