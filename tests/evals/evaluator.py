"""Evaluator metrics and scoring engine for SRE AI investigations."""

from typing import Any
from pydantic import BaseModel, Field
from shepherd.domain.schemas import FinalReport
from tests.evals.golden_incidents import GoldenIncident


class EvalMetricResult(BaseModel):
    metric_name: str
    score: float = Field(ge=0.0, le=1.0)
    passed: bool
    details: str


class InvestigationEvalReport(BaseModel):
    incident_id: str
    overall_passed: bool
    total_score: float = Field(ge=0.0, le=1.0)
    metrics: list[EvalMetricResult]


class InvestigationEvaluator:
    """Evaluates generated incident reports against golden benchmarks."""

    @staticmethod
    def evaluate_rca_accuracy(report: FinalReport, golden: GoldenIncident) -> EvalMetricResult:
        """Evaluates whether the primary root cause and category match the golden ground truth."""
        primary_rc = (report.primary_root_cause or "").lower()
        matched_keywords = [k for k in golden.expected_keywords if k.lower() in primary_rc]
        keyword_score = len(matched_keywords) / max(len(golden.expected_keywords), 1)

        category_match = report.category == golden.expected_category or report.category.value.lower() in golden.expected_category.value.lower()
        category_score = 1.0 if category_match else 0.5

        combined_score = round(0.6 * min(keyword_score * 2.0, 1.0) + 0.4 * category_score, 2)
        passed = combined_score >= 0.7

        return EvalMetricResult(
            metric_name="root_cause_accuracy",
            score=min(combined_score, 1.0),
            passed=passed,
            details=f"Matched {len(matched_keywords)}/{len(golden.expected_keywords)} keywords. Category match: {category_match}",
        )

    @staticmethod
    def evaluate_cross_validation(report: FinalReport, golden: GoldenIncident) -> EvalMetricResult:
        """Verifies multi-specialist cross-validation and confidence."""
        cv_match = report.cross_validated == golden.expected_cross_validated
        confidence_ok = report.confidence in [golden.min_confidence, "high"]

        score = 1.0 if (cv_match and confidence_ok) else (0.5 if cv_match else 0.0)
        passed = score >= 0.7

        return EvalMetricResult(
            metric_name="cross_validation_integrity",
            score=score,
            passed=passed,
            details=f"Cross-validated: {report.cross_validated}, Confidence: {report.confidence}",
        )

    @staticmethod
    def evaluate_evidence_chain(report: FinalReport, golden: GoldenIncident) -> EvalMetricResult:
        """Verifies depth and presence of telemetry evidence chain."""
        ev_count = len(report.evidence_chain)
        passed = ev_count >= golden.min_evidence_count
        score = min(ev_count / max(golden.min_evidence_count, 1), 1.0)

        return EvalMetricResult(
            metric_name="evidence_chain_completeness",
            score=score,
            passed=passed,
            details=f"Found {ev_count} evidence items (minimum required: {golden.min_evidence_count})",
        )

    @staticmethod
    def evaluate_recommendations(report: FinalReport) -> EvalMetricResult:
        """Checks if immediate and short-term actionable recommendations are present."""
        has_immediate = len(report.immediate_recommendations) > 0
        has_short_term = len(report.short_term_recommendations) > 0

        score = 1.0 if (has_immediate and has_short_term) else (0.5 if (has_immediate or has_short_term) else 0.0)
        passed = score >= 0.5

        return EvalMetricResult(
            metric_name="actionable_recommendations",
            score=score,
            passed=passed,
            details=f"Immediate recs: {len(report.immediate_recommendations)}, Short-term recs: {len(report.short_term_recommendations)}",
        )

    @classmethod
    def evaluate_full_investigation(cls, report: FinalReport, golden: GoldenIncident) -> InvestigationEvalReport:
        """Runs all evaluation metrics on an investigation report."""
        metrics = [
            cls.evaluate_rca_accuracy(report, golden),
            cls.evaluate_cross_validation(report, golden),
            cls.evaluate_evidence_chain(report, golden),
            cls.evaluate_recommendations(report),
        ]

        total_score = round(sum(m.score for m in metrics) / len(metrics), 2)
        overall_passed = all(m.passed for m in metrics) and total_score >= 0.7

        return InvestigationEvalReport(
            incident_id=golden.incident_id,
            overall_passed=overall_passed,
            total_score=total_score,
            metrics=metrics,
        )
