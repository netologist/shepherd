"""LangGraph engine exports for SRE AI multi-agent investigation."""

from typing import Any
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver as BaseCheckpointer
from langgraph.graph.state import CompiledStateGraph


class ShepherdMemorySaver(MemorySaver):
    """MemorySaver checkpointer with helper methods for direct state lookup."""

    async def get_state(self, thread_id: str) -> dict[str, Any] | None:
        config = {"configurable": {"thread_id": thread_id}}
        t = self.get_tuple(config)
        if t and t.checkpoint:
            channel_vals = t.checkpoint.get("channel_values", {})
            return dict(channel_vals)
        return None

    async def put_state(self, thread_id: str, state: dict[str, Any]) -> None:
        # State updates are handled through LangGraph's native checkpointing
        pass


__all__ = [
    "StateGraph",
    "START",
    "END",
    "Send",
    "MemorySaver",
    "ShepherdMemorySaver",
    "BaseCheckpointer",
    "CompiledStateGraph",
]
