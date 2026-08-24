"""FastAPI REST & Webhook server for SRE AI Investigation Platform."""

from typing import Any
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sre_ai.domain.schemas import InvestigationType, FeedbackReview
from sre_ai.graph.router import SREEntryRouter

app = FastAPI(
    title="SRE AI Multi-Agent Investigation API",
    description="Automated incident investigation, root cause analysis, and post-investigation chat service.",
    version="0.1.0",
)

router = SREEntryRouter()


class StartInvestigationRequest(BaseModel):
    raw_input: str = Field(description="Incident description, ticket payload, or alert query")
    investigation_type: InvestigationType = Field(
        default=InvestigationType.INCIDENT_REVIEW,
        description="Investigation type: incident-review, oncall-alert-analyzer, qa-support, cluster-resource-alert",
    )
    investigation_id: str | None = Field(default=None, description="Optional custom investigation ID")


class ChatRequest(BaseModel):
    message: str = Field(description="User follow-up question or assignment for the agent")


class ChatResponse(BaseModel):
    investigation_id: str
    reply: str


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "sre-ai"}


@app.post("/api/v1/investigations", status_code=status.HTTP_201_CREATED)
async def create_investigation(req: StartInvestigationRequest) -> dict[str, Any]:
    """Triggers an automated incident investigation."""
    try:
        final_state = await router.start_investigation(
            raw_input=req.raw_input,
            investigation_type=req.investigation_type,
            investigation_id=req.investigation_id,
        )
        return {
            "investigation_id": final_state["investigation_id"],
            "status": "completed",
            "final_report": final_state.get("final_report"),
            "findings_by_domain": final_state.get("findings_by_domain"),
            "correlation_result": final_state.get("correlation_result"),
            "deep_dive_count": final_state.get("deep_dive_count", 0),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation execution failed: {str(e)}",
        )


@app.get("/api/v1/investigations/{investigation_id}")
async def get_investigation(investigation_id: str) -> dict[str, Any]:
    """Retrieves an existing investigation state by ID."""
    state = await router.checkpointer.get_state(investigation_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation '{investigation_id}' not found.",
        )
    return {
        "investigation_id": investigation_id,
        "final_report": state.get("final_report"),
        "findings_by_domain": state.get("findings_by_domain"),
        "correlation_result": state.get("correlation_result"),
        "deep_dive_count": state.get("deep_dive_count", 0),
        "chat_history": state.get("chat_history", []),
    }


@app.post("/api/v1/investigations/{investigation_id}/chat")
async def chat_investigation(investigation_id: str, req: ChatRequest) -> ChatResponse:
    """Interacts with the Post-Investigation Chat Agent on top of an existing investigation."""
    reply = await router.send_chat_message(investigation_id, req.message)
    return ChatResponse(investigation_id=investigation_id, reply=reply)


@app.post("/api/v1/feedback", status_code=status.HTTP_201_CREATED)
async def submit_feedback(feedback: FeedbackReview) -> dict[str, str]:
    """Submits 1-5 star user review and comments."""
    router.submit_feedback(feedback)
    return {"status": "feedback_recorded", "investigation_id": feedback.investigation_id}


@app.get("/api/v1/analytics/feedback")
async def get_feedback_analytics() -> dict[str, Any]:
    """Returns aggregated feedback analytics."""
    return {
        "total_reviews": len(router.feedback_store),
        "average_rating": router.get_average_rating(),
        "recent_reviews": [f.model_dump() for f in router.feedback_store[-10:]],
    }
