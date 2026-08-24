"""Model profiles and multi-tier routing mapping."""

from pydantic import BaseModel, Field
from sre_ai.domain.schemas import InvestigationType


class PhaseModelProfile(BaseModel):
    gather_model: str = Field(default="gemini/gemini-2.5-flash")
    specialist_model: str = Field(default="gemini/gemini-2.5-pro")
    correlate_model: str = Field(default="anthropic/claude-3-7-sonnet")
    evaluate_model: str = Field(default="anthropic/claude-3-7-sonnet")
    synthesize_model: str = Field(default="anthropic/claude-3-7-sonnet")
    chat_model: str = Field(default="anthropic/claude-3-7-sonnet")
    fallback_chain: list[str] = Field(
        default_factory=lambda: [
            "anthropic/claude-3-7-sonnet",
            "openai/gpt-4o",
            "gemini/gemini-2.5-flash",
        ]
    )


MODEL_PROFILES: dict[InvestigationType, PhaseModelProfile] = {
    InvestigationType.INCIDENT_REVIEW: PhaseModelProfile(
        gather_model="gemini/gemini-2.5-flash",
        specialist_model="gemini/gemini-2.5-pro",
        correlate_model="anthropic/claude-3-7-sonnet",
        evaluate_model="anthropic/claude-3-7-sonnet",
        synthesize_model="anthropic/claude-3-7-sonnet",
        chat_model="anthropic/claude-3-7-sonnet",
        fallback_chain=["anthropic/claude-3-7-sonnet", "openai/gpt-4o", "gemini/gemini-2.5-flash"],
    ),
    InvestigationType.ONCALL_ALERT: PhaseModelProfile(
        gather_model="gemini/gemini-2.5-flash",
        specialist_model="gemini/gemini-2.5-pro",
        correlate_model="gemini/gemini-2.5-pro",
        evaluate_model="gemini/gemini-2.5-pro",
        synthesize_model="gemini/gemini-2.5-pro",
        chat_model="gemini/gemini-2.5-pro",
        fallback_chain=["gemini/gemini-2.5-pro", "openai/gpt-4o-mini"],
    ),
    InvestigationType.QA_SUPPORT: PhaseModelProfile(
        gather_model="gemini/gemini-2.5-flash",
        specialist_model="deepseek/deepseek-chat",
        correlate_model="deepseek/deepseek-chat",
        evaluate_model="deepseek/deepseek-chat",
        synthesize_model="deepseek/deepseek-chat",
        chat_model="deepseek/deepseek-chat",
        fallback_chain=["deepseek/deepseek-chat", "openai/gpt-4o-mini"],
    ),
    InvestigationType.CLUSTER_RESOURCE_ALERT: PhaseModelProfile(
        gather_model="gemini/gemini-2.5-flash",
        specialist_model="gemini/gemini-2.5-flash",
        correlate_model="gemini/gemini-2.5-flash",
        evaluate_model="gemini/gemini-2.5-flash",
        synthesize_model="gemini/gemini-2.5-flash",
        chat_model="gemini/gemini-2.5-flash",
        fallback_chain=["gemini/gemini-2.5-flash", "openai/gpt-4o-mini"],
    ),
}


def get_model_profile(inv_type: InvestigationType | str) -> PhaseModelProfile:
    if isinstance(inv_type, str):
        try:
            inv_type = InvestigationType(inv_type)
        except ValueError:
            inv_type = InvestigationType.INCIDENT_REVIEW
    return MODEL_PROFILES.get(inv_type, MODEL_PROFILES[InvestigationType.INCIDENT_REVIEW])
