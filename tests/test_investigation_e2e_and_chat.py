"""End-to-End Investigation, Post-Investigation Chat, and FastAPI tests."""

import pytest
from httpx import AsyncClient, ASGITransport
from sre_ai.graph.router import SREEntryRouter
from sre_ai.domain.schemas import InvestigationType, FeedbackReview
from sre_ai.server.app import app


@pytest.mark.asyncio
async def test_end_to_end_investigation_and_chat_flow():
    router = SREEntryRouter()

    # 1. Trigger full automated investigation
    raw_prompt = "Incident INC-1042: Checkout service latency spiked to 3s and 5xx errors started appearing on order-db"
    result = await router.start_investigation(
        raw_input=raw_prompt,
        investigation_type=InvestigationType.INCIDENT_REVIEW,
        investigation_id="inv-e2e-001",
    )

    assert result["investigation_id"] == "inv-e2e-001"
    assert result["current_phase"] == "investigation_complete"

    final_report = result.get("final_report")
    assert final_report is not None
    assert final_report["incident_id"] == "INC-1042"
    assert "database" in final_report["category"].lower() or "pool" in final_report["primary_root_cause"].lower()
    assert len(final_report["root_cause_hypotheses"]) > 0
    assert len(final_report["evidence_chain"]) > 0

    # 2. Interactive Post-Investigation Chat on the completed checkpoint
    chat_reply = await router.send_chat_message(
        investigation_id="inv-e2e-001",
        message="Can you explain why the database connection pool starved?",
    )
    assert len(chat_reply) > 0
    assert "investigation" in chat_reply.lower() or "connection" in chat_reply.lower() or "database" in chat_reply.lower()

    # Verify chat history was saved to checkpointer
    saved = await router.checkpointer.get_state("inv-e2e-001")
    assert saved is not None
    assert len(saved.get("chat_history", [])) == 2

    # 3. Submit Feedback Review
    feedback = FeedbackReview(
        investigation_id="inv-e2e-001",
        rating=5,
        comment="Great RCA, pinpointed order-db connection pool immediately.",
        reviewer="sre-oncall@trendyol.com",
    )
    router.submit_feedback(feedback)
    assert router.get_average_rating() == 5.0


@pytest.mark.asyncio
async def test_fastapi_server_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Health check
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "healthy"

        # Create investigation
        create_resp = await client.post(
            "/api/v1/investigations",
            json={
                "raw_input": "INC-999: High error rate on payment service",
                "investigation_type": "incident-review",
                "investigation_id": "inv-fastapi-test",
            },
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["investigation_id"] == "inv-fastapi-test"
        assert data["final_report"] is not None

        # Get investigation
        get_resp = await client.get("/api/v1/investigations/inv-fastapi-test")
        assert get_resp.status_code == 200
        assert get_resp.json()["investigation_id"] == "inv-fastapi-test"

        # Chat
        chat_resp = await client.post(
            "/api/v1/investigations/inv-fastapi-test/chat",
            json={"message": "What were the affected services?"},
        )
        assert chat_resp.status_code == 200
        assert len(chat_resp.json()["reply"]) > 0

        # Submit feedback
        fb_resp = await client.post(
            "/api/v1/feedback",
            json={
                "investigation_id": "inv-fastapi-test",
                "rating": 4,
                "comment": "Accurate findings",
                "reviewer": "engineer@company.com",
            },
        )
        assert fb_resp.status_code == 201

        # Get feedback analytics
        analytics_resp = await client.get("/api/v1/analytics/feedback")
        assert analytics_resp.status_code == 200
        analytics = analytics_resp.json()
        assert analytics["total_reviews"] >= 1
        assert analytics["average_rating"] > 0
