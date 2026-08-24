"""Runtime guardrails for specialist tool execution."""

import hashlib
import json
from typing import Any


class ToolGuardrailTracker:
    """Tracks and enforces limits on agent tool loops to prevent runaway iterations and token explosion."""

    def __init__(
        self,
        max_iterations: int = 15,
        max_result_chars: int = 50_000,
        max_cumulative_chars: int = 800_000,
    ):
        self.max_iterations = max_iterations
        self.max_result_chars = max_result_chars
        self.max_cumulative_chars = max_cumulative_chars

        self.current_iteration = 0
        self.cumulative_chars = 0
        self._seen_tool_calls: set[str] = set()
        self.is_exhausted = False
        self.budget_exceeded = False

    def _hash_call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        canonical_json = json.dumps(arguments, sort_keys=True, default=str)
        return hashlib.sha256(f"{tool_name}:{canonical_json}".encode("utf-8")).hexdigest()

    def check_and_record_call(self, tool_name: str, arguments: dict[str, Any]) -> str | None:
        """Checks if a tool call is permitted. Returns an error notice if blocked, or None if allowed."""
        if self.current_iteration >= self.max_iterations:
            self.is_exhausted = True
            return f"Notice: Maximum tool iteration limit ({self.max_iterations}) reached. Synthesize findings immediately."

        if self.cumulative_chars >= self.max_cumulative_chars:
            self.budget_exceeded = True
            return f"Notice: Cumulative token/character budget exceeded ({self.cumulative_chars} chars). Synthesize findings immediately."

        call_hash = self._hash_call(tool_name, arguments)
        if call_hash in self._seen_tool_calls:
            return (
                f"Notice: Duplicate call to '{tool_name}' with identical arguments was suppressed. "
                "Review the previous response above to continue your investigation."
            )

        self._seen_tool_calls.add(call_hash)
        self.current_iteration += 1
        return None

    def process_tool_result(self, raw_result: str) -> str:
        """Enforces character caps on single results and tracks cumulative usage."""
        char_count = len(raw_result)
        if char_count > self.max_result_chars:
            truncated = (
                raw_result[: self.max_result_chars]
                + f"\n\n... [TRUNCATED: Response exceeded {self.max_result_chars} character limit] ..."
            )
            self.cumulative_chars += len(truncated)
            return truncated

        self.cumulative_chars += char_count
        return raw_result
