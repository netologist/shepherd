"""Deep Dive Dispatcher Node."""

from typing import Any
from sre_ai.domain.schemas import DeepDiveTask
from sre_ai.agents.specialists.registry import specialist_registry


class DeepDiveDispatcher:
    """Prepares targeted deep dive instructions for named specialists."""

    @staticmethod
    def prepare_deep_dive_targets(
        tasks: list[DeepDiveTask],
    ) -> list[dict[str, Any]]:
        """Normalizes specialist names and bundles instructions for parallel LangGraph dispatch."""
        dispatches: list[dict[str, Any]] = []

        for task in tasks:
            canonical_domain = specialist_registry.normalize_name(task.specialist)
            instruction = f"Targeted Deep-Dive Question: {task.question}"
            if task.target_service:
                instruction += f"\nTarget Service: {task.target_service}"
            if task.time_window:
                instruction += f"\nTime Window: {task.time_window}"

            dispatches.append({
                "domain": canonical_domain,
                "additional_instructions": instruction,
            })

        return dispatches
