"""Entry Router coordinating new investigations and post-investigation chat."""

from typing import Any
import uuid
from sre_ai.domain.schemas import FinalReport, IncidentContext, FeedbackReview, InvestigationType
from sre_ai.graph.builder import build_investigation_graph
from sre_ai.graph.engine import BaseCheckpointer, MemorySaver
from sre_ai.agents.chat import PostInvestigationChatAgent


class SREEntryRouter:
    """Coordinates entry between new automated investigations and stateful post-investigation chat."""

    def __init__(self, checkpointer: BaseCheckpointer | None = None):
        self.checkpointer = checkpointer or MemorySaver()
        self.graph = build_investigation_graph(checkpointer=self.checkpointer)
        self.chat_agent = PostInvestigationChatAgent()
        self.feedback_store: list[FeedbackReview] = []

    async def start_investigation(
        self,
        raw_input: str,
        investigation_type: InvestigationType = InvestigationType.INCIDENT_REVIEW,
        investigation_id: str | None = None,
    ) -> dict[str, Any]:
        """Triggers a full automated investigation run."""
        inv_id = investigation_id or f"inv-{uuid.uuid4().hex[:8]}"

        initial_state = {
            "investigation_id": inv_id,
            "investigation_type": investigation_type.value if hasattr(investigation_type, "value") else str(investigation_type),
            "raw_input": raw_input,
            "incident_context": None,
            "investigation_brief": None,
            "prefetched_data": {},
            "findings_by_domain": {},
            "correlation_result": None,
            "evaluation_result": None,
            "deep_dive_count": 0,
            "suggested_deep_dives": [],
            "final_report": None,
            "chat_history": [],
            "current_phase": "initiated",
        }

        config = {"configurable": {"thread_id": inv_id}}
        final_state = await self.graph.ainvoke(initial_state, config=config)
        return final_state

    async def send_chat_message(
        self,
        investigation_id: str,
        message: str,
    ) -> str:
        """Handles interactive follow-up questions on an existing completed investigation."""
        saved_state = await self.checkpointer.get_state(investigation_id)
        if not saved_state:
            return f"Investigation '{investigation_id}' not found. Please start an investigation first."

        final_report_data = saved_state.get("final_report")
        report = FinalReport.model_validate(final_report_data) if final_report_data else None

        ctx_data = saved_state.get("incident_context")
        context = IncidentContext.model_validate(ctx_data) if ctx_data else None

        findings = saved_state.get("findings_by_domain") or {}
        chat_history = saved_state.get("chat_history") or []

        reply = await self.chat_agent.chat(
            user_message=message,
            final_report=report,
            context=context,
            findings_by_domain=findings,
            conversation_history=chat_history,
        )

        # Update chat history in checkpoint
        updated_history = list(chat_history)
        updated_history.append({"role": "user", "content": message})
        updated_history.append({"role": "assistant", "content": reply})

        saved_state["chat_history"] = updated_history
        await self.checkpointer.put_state(investigation_id, saved_state)

        return reply

    def submit_feedback(self, feedback: FeedbackReview) -> None:
        """Stores user review and rating."""
        self.feedback_store.append(feedback)

    def get_average_rating(self) -> float:
        if not self.feedback_store:
            return 0.0
        return sum(f.rating for f in self.feedback_store) / len(self.feedback_store)
