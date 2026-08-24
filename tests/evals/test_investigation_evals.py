"""Comprehensive Evaluation Tests for SRE AI Autonomous RCA Pipeline."""

import pytest
from shepherd.graph.router import SREEntryRouter
from shepherd.domain.schemas import FinalReport
from tests.evals.golden_incidents import GOLDEN_INCIDENTS, GoldenIncident
from tests.evals.evaluator import InvestigationEvaluator


@pytest.mark.asyncio
@pytest.mark.parametrize("golden", GOLDEN_INCIDENTS, ids=lambda g: g.incident_id)
async def test_golden_incident_investigation_eval(golden: GoldenIncident):
    """Evaluates an automated investigation against golden incident benchmarks."""
    router = SREEntryRouter()

    result = await router.start_investigation(
        raw_input=golden.raw_prompt,
        investigation_type=golden.investigation_type,
        investigation_id=f"eval-{golden.incident_id.lower()}",
    )

    assert result["investigation_id"] == f"eval-{golden.incident_id.lower()}"
    assert result["current_phase"] == "investigation_complete"

    final_report_data = result.get("final_report")
    assert final_report_data is not None, "FinalReport must be produced by investigation"

    report = FinalReport.model_validate(final_report_data)

    # Run evaluation suite
    eval_summary = InvestigationEvaluator.evaluate_full_investigation(report, golden)

    # Print evaluation metrics for visibility
    print(f"\n[EVAL REPORT] {golden.incident_id} Total Score: {eval_summary.total_score} (Passed: {eval_summary.overall_passed})")
    for m in eval_summary.metrics:
        print(f"  - {m.metric_name}: score={m.score:.2f}, passed={m.passed} ({m.details})")

    # Assert evaluation criteria
    assert eval_summary.total_score >= 0.7, f"Total evaluation score ({eval_summary.total_score}) below threshold (0.7)"
    assert eval_summary.overall_passed is True, f"Incident {golden.incident_id} failed evaluation gates"


@pytest.mark.asyncio
async def test_chat_agent_evaluation():
    """Evaluates post-investigation interactive chat turn for relevance and correctness."""
    golden = GOLDEN_INCIDENTS[0]  # INC-8088
    router = SREEntryRouter()

    # Seed investigation
    await router.start_investigation(
        raw_input=golden.raw_prompt,
        investigation_type=golden.investigation_type,
        investigation_id="eval-chat-turn",
    )

    # Perform chat turn
    reply = await router.send_chat_message(
        investigation_id="eval-chat-turn",
        message=golden.sample_chat_query,
    )

    assert len(reply) > 0, "Chat agent must reply to SRE question"
    reply_lower = reply.lower()

    matched_keywords = [k for k in golden.expected_chat_keywords if k.lower() in reply_lower]
    keyword_coverage = len(matched_keywords) / len(golden.expected_chat_keywords)

    print(f"\n[CHAT EVAL] Question: '{golden.sample_chat_query}' | Reply: '{reply[:120]}...'")
    print(f"  Matched {len(matched_keywords)}/{len(golden.expected_chat_keywords)} expected keywords (coverage: {keyword_coverage:.2f})")

    assert keyword_coverage >= 0.5, f"Chat response keyword coverage ({keyword_coverage}) below 0.5"
