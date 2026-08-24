"""Pure Python LangGraph-compatible StateGraph and Checkpointer execution engine."""

import asyncio
import inspect
from typing import Any, Callable, get_type_hints, get_origin, get_args
from dataclasses import dataclass


@dataclass
class Send:
    """Represents a dynamic parallel fan-out dispatch to a specific node with an argument."""
    node: str
    arg: Any


class BaseCheckpointer:
    """Base interface for checkpoint storage."""

    async def get_state(self, thread_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    async def put_state(self, thread_id: str, state: dict[str, Any]) -> None:
        raise NotImplementedError


class MemorySaver(BaseCheckpointer):
    """In-memory checkpointer indexed by thread_id / investigation_id."""

    def __init__(self):
        self._storage: dict[str, dict[str, Any]] = {}

    async def get_state(self, thread_id: str) -> dict[str, Any] | None:
        if thread_id in self._storage:
            return dict(self._storage[thread_id])
        return None

    async def put_state(self, thread_id: str, state: dict[str, Any]) -> None:
        self._storage[thread_id] = dict(state)


class CompiledStateGraph:
    """Compiled executable state graph with Send fan-out and checkpointer support."""

    def __init__(
        self,
        nodes: dict[str, Callable[..., Any]],
        edges: dict[str, str],
        conditional_edges: dict[str, tuple[Callable[..., Any], dict[str, str] | None]],
        entry_point: str,
        state_schema: type,
        checkpointer: BaseCheckpointer | None = None,
    ):
        self.nodes = nodes
        self.edges = edges
        self.conditional_edges = conditional_edges
        self.entry_point = entry_point
        self.state_schema = state_schema
        self.checkpointer = checkpointer
        self._reducers = self._extract_reducers(state_schema)

    def _extract_reducers(self, schema: type) -> dict[str, Callable[[Any, Any], Any]]:
        reducers: dict[str, Callable[[Any, Any], Any]] = {}
        try:
            hints = get_type_hints(schema, include_extras=True)
            for key, hint in hints.items():
                if get_origin(hint) is getattr(asyncio, "_AnnotatedAlias", None) or str(type(hint)) == "<class 'typing._AnnotatedAlias'>":
                    args = get_args(hint)
                    if len(args) > 1 and callable(args[1]):
                        reducers[key] = args[1]
        except Exception:
            pass
        return reducers

    def _apply_update(self, current_state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        new_state = dict(current_state)
        for k, v in update.items():
            if k in self._reducers:
                reducer = self._reducers[k]
                new_state[k] = reducer(new_state.get(k), v)
            else:
                new_state[k] = v
        return new_state

    async def ainvoke(
        self,
        initial_input: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Executes the graph to completion."""
        thread_id = (config or {}).get("configurable", {}).get("thread_id", "default")

        # Load state from checkpointer if present
        state: dict[str, Any] = {}
        if self.checkpointer:
            saved = await self.checkpointer.get_state(thread_id)
            if saved:
                state = dict(saved)

        # Merge input into state
        state = self._apply_update(state, initial_input)

        current_node = self.entry_point
        visited_steps = 0
        max_steps = 100

        while current_node and visited_steps < max_steps:
            visited_steps += 1
            node_fn = self.nodes.get(current_node)
            if not node_fn:
                break

            # Execute node
            if inspect.iscoroutinefunction(node_fn):
                update = await node_fn(state)
            else:
                update = node_fn(state)

            if update and isinstance(update, dict):
                state = self._apply_update(state, update)

            # Determine next routing
            if current_node in self.conditional_edges:
                router_fn, path_map = self.conditional_edges[current_node]

                if inspect.iscoroutinefunction(router_fn):
                    router_output = await router_fn(state)
                else:
                    router_output = router_fn(state)

                # Check if router returned dynamic Send() fan-out
                if isinstance(router_output, list) and router_output and isinstance(router_output[0], Send):
                    # Execute all Send dispatches in parallel
                    send_tasks = []
                    for send_item in router_output:
                        target_fn = self.nodes.get(send_item.node)
                        if target_fn:
                            if inspect.iscoroutinefunction(target_fn):
                                send_tasks.append(target_fn(send_item.arg))
                            else:
                                send_tasks.append(asyncio.to_thread(target_fn, send_item.arg))

                    if send_tasks:
                        results = await asyncio.gather(*send_tasks, return_exceptions=True)
                        for res in results:
                            if isinstance(res, dict):
                                state = self._apply_update(state, res)

                    # Default edge after fan-out completes
                    current_node = self.edges.get(current_node)
                elif isinstance(router_output, str):
                    target = path_map.get(router_output, router_output) if path_map else router_output
                    current_node = target
                else:
                    current_node = self.edges.get(current_node)
            else:
                current_node = self.edges.get(current_node)

        # Save final state to checkpointer
        if self.checkpointer:
            await self.checkpointer.put_state(thread_id, state)

        return state


class StateGraph:
    """Graph builder configuring nodes, edges, and conditional paths."""

    def __init__(self, state_schema: type):
        self.state_schema = state_schema
        self.nodes: dict[str, Callable[..., Any]] = {}
        self.edges: dict[str, str] = {}
        self.conditional_edges: dict[str, tuple[Callable[..., Any], dict[str, str] | None]] = {}
        self.entry_point: str | None = None

    def add_node(self, name: str, func: Callable[..., Any]) -> None:
        self.nodes[name] = func

    def add_edge(self, start_key: str, end_key: str) -> None:
        self.edges[start_key] = end_key

    def add_conditional_edges(
        self,
        source: str,
        path: Callable[..., Any],
        path_map: dict[str, str] | None = None,
    ) -> None:
        self.conditional_edges[source] = (path, path_map)

    def set_entry_point(self, key: str) -> None:
        self.entry_point = key

    def compile(self, checkpointer: BaseCheckpointer | None = None) -> CompiledStateGraph:
        if not self.entry_point:
            raise ValueError("StateGraph entry point must be set before compilation.")
        return CompiledStateGraph(
            nodes=self.nodes,
            edges=self.edges,
            conditional_edges=self.conditional_edges,
            entry_point=self.entry_point,
            state_schema=self.state_schema,
            checkpointer=checkpointer,
        )
