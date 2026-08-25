"""PlaybookRunbook specialist: LlamaIndex ReActAgent over an in-memory playbook knowledge base.

Design rationale: playbook/runbook retrieval is fundamentally a retrieval-augmented reasoning
task rather than a telemetry-query task.  LlamaIndex ReActAgent gives us:
  - Transparent tool-use trace (Thought / Action / Observation loop)
  - Native async support via WorkflowHandler
  - FunctionTool wrapping of existing MCP clients
  - Composable with our fallback-LLM stack via llama-index-llms-* adapters

The agent receives an IncidentContext + CorrelationResult and returns PlaybookFindings.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from llama_index.core.agent import ReActAgent  # type: ignore[import-untyped]
from llama_index.core.tools import FunctionTool  # type: ignore[import-untyped]
from llama_index.core.llms import MockLLM  # type: ignore[import-untyped]

from shepherd.domain.schemas import (
    IncidentContext,
    CorrelationResult,
    PlaybookFindings,
    PlaybookMatch,
    RunbookStep,
)
from shepherd.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inline playbook knowledge base
# In production this would be backed by a vector store (e.g. pgvector / Qdrant)
# indexed over your Confluence / GitHub wiki runbooks.
# ---------------------------------------------------------------------------
_PLAYBOOKS: list[dict[str, Any]] = [
    {
        "id": "PB-001",
        "title": "OOMKill Remediation",
        "keywords": ["oomkill", "oom", "memory", "killed", "evicted", "container"],
        "summary": "Remediate pods terminated due to memory limit breaches.",
        "steps": [
            {"action": "Identify OOMKilled pods", "command": "kubectl get pods -A | grep OOMKilled", "expected_outcome": "List of affected pods", "rollback": None},
            {"action": "Inspect memory metrics", "command": "kubectl top pods -n {namespace}", "expected_outcome": "Current memory consumption visible", "rollback": None},
            {"action": "Increase memory limits in Deployment manifest", "command": "kubectl set resources deployment/{app} --limits=memory=512Mi -n {namespace}", "expected_outcome": "Pods restart within limits", "rollback": "kubectl set resources deployment/{app} --limits=memory=256Mi -n {namespace}"},
            {"action": "Verify pod stability", "command": "kubectl rollout status deployment/{app} -n {namespace}", "expected_outcome": "Rollout completes with no new OOMKills", "rollback": None},
        ],
        "escalation": ["#sre-oncall", "platform-team@company.com"],
    },
    {
        "id": "PB-002",
        "title": "High Latency / P99 Degradation",
        "keywords": ["latency", "p99", "slow", "timeout", "response time", "degradation"],
        "summary": "Diagnose and remediate elevated P99 latency across service endpoints.",
        "steps": [
            {"action": "Check upstream dependencies", "command": "kubectl exec -it {pod} -- curl -o /dev/null -s -w '%{time_total}' http://dependency-svc/health", "expected_outcome": "Identify slow upstream", "rollback": None},
            {"action": "Scale up affected deployment", "command": "kubectl scale deployment/{app} --replicas=6 -n {namespace}", "expected_outcome": "Latency recovers under increased parallelism", "rollback": "kubectl scale deployment/{app} --replicas=3 -n {namespace}"},
            {"action": "Enable circuit breaker", "command": "kubectl annotate svc/{app} sre.io/circuit-breaker=enabled", "expected_outcome": "Downstream callers fail fast instead of queueing", "rollback": "kubectl annotate svc/{app} sre.io/circuit-breaker-"},
        ],
        "escalation": ["#backend-oncall"],
    },
    {
        "id": "PB-003",
        "title": "Database Connection Pool Exhaustion",
        "keywords": ["database", "db", "connection", "pool", "exhaustion", "lock", "timeout", "postgres", "mysql"],
        "summary": "Recover from saturated database connection pools causing cascading timeouts.",
        "steps": [
            {"action": "Check active connections", "command": "kubectl exec -it {db_pod} -- psql -c 'SELECT count(*) FROM pg_stat_activity;'", "expected_outcome": "Connection count near max_connections limit", "rollback": None},
            {"action": "Kill idle connections older than 5 min", "command": "kubectl exec -it {db_pod} -- psql -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='idle' AND query_start < NOW() - INTERVAL '5 minutes';\"", "expected_outcome": "Connection count drops below 80%", "rollback": None},
            {"action": "Restart PgBouncer / connection pooler", "command": "kubectl rollout restart deployment/pgbouncer -n {namespace}", "expected_outcome": "Connection pooler reconnects cleanly", "rollback": None},
        ],
        "escalation": ["#data-platform-oncall", "dba@company.com"],
    },
    {
        "id": "PB-004",
        "title": "Node Not Ready / Node Pressure",
        "keywords": ["node", "not ready", "notready", "pressure", "disk", "pid", "cordoned", "taint"],
        "summary": "Recover unhealthy Kubernetes nodes without disrupting running workloads.",
        "steps": [
            {"action": "Cordon the unhealthy node", "command": "kubectl cordon {node}", "expected_outcome": "No new pods scheduled on this node", "rollback": "kubectl uncordon {node}"},
            {"action": "Drain workloads safely", "command": "kubectl drain {node} --ignore-daemonsets --delete-emptydir-data --grace-period=60", "expected_outcome": "All evictable pods rescheduled", "rollback": None},
            {"action": "Inspect kubelet logs", "command": "journalctl -u kubelet -n 100 --no-pager", "expected_outcome": "Root cause of NotReady visible (disk/memory/network)", "rollback": None},
            {"action": "Uncordon after remediation", "command": "kubectl uncordon {node}", "expected_outcome": "Node returns to Ready state", "rollback": "kubectl cordon {node}"},
        ],
        "escalation": ["#infra-oncall"],
    },
    {
        "id": "PB-005",
        "title": "Deployment Rollback",
        "keywords": ["deployment", "rollout", "rollback", "bad deploy", "crashloopbackoff", "crash", "5xx spike"],
        "summary": "Roll back a bad deployment that introduced regressions.",
        "steps": [
            {"action": "Check rollout history", "command": "kubectl rollout history deployment/{app} -n {namespace}", "expected_outcome": "Previous revision visible", "rollback": None},
            {"action": "Roll back to previous revision", "command": "kubectl rollout undo deployment/{app} -n {namespace}", "expected_outcome": "Previous stable version running", "rollback": "kubectl rollout undo deployment/{app} -n {namespace} --to-revision=N"},
            {"action": "Verify rollback health", "command": "kubectl rollout status deployment/{app} -n {namespace}", "expected_outcome": "All replicas available on previous image", "rollback": None},
        ],
        "escalation": ["#sre-oncall", "#releases"],
    },
]


def _keyword_score(playbook: dict[str, Any], query: str) -> float:
    """Simple keyword overlap score — no embedding needed for in-process lookup."""
    q_lower = query.lower()
    hits = sum(1 for kw in playbook["keywords"] if kw in q_lower)
    return round(hits / max(len(playbook["keywords"]), 1), 3)


# ---------------------------------------------------------------------------
# FunctionTools exposed to the LlamaIndex ReActAgent
# ---------------------------------------------------------------------------

def search_playbooks(query: str) -> str:
    """Search the SRE playbook knowledge base for remediation runbooks matching the incident description.

    Args:
        query: Incident description or root cause summary to match against playbooks.

    Returns:
        JSON-like string listing matching playbook IDs, titles, and relevance scores.
    """
    scored = [
        (pb, _keyword_score(pb, query))
        for pb in _PLAYBOOKS
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:3]
    lines = [f"[{pb['id']}] {pb['title']} (score={score:.2f}): {pb['summary']}" for pb, score in top if score > 0]
    if not lines:
        return "No matching playbooks found. Consider escalating to the on-call rotation."
    return "Matching playbooks:\n" + "\n".join(lines)


def get_playbook_steps(playbook_id: str) -> str:
    """Retrieve the full remediation steps for a specific playbook by its ID.

    Args:
        playbook_id: Playbook identifier (e.g. 'PB-001').

    Returns:
        Ordered remediation steps with commands and expected outcomes.
    """
    for pb in _PLAYBOOKS:
        if pb["id"].upper() == playbook_id.upper():
            lines = [f"# {pb['title']}", pb["summary"], ""]
            for i, step in enumerate(pb["steps"], 1):
                lines.append(f"**Step {i}:** {step['action']}")
                if step.get("command"):
                    lines.append(f"  Command: `{step['command']}`")
                lines.append(f"  Expected: {step['expected_outcome']}")
                if step.get("rollback"):
                    lines.append(f"  Rollback: `{step['rollback']}`")
            lines.append(f"\nEscalation: {', '.join(pb['escalation'])}")
            return "\n".join(lines)
    return f"Playbook '{playbook_id}' not found."


def get_escalation_path(category: str) -> str:
    """Retrieve the escalation contacts for a root cause category when no playbook matches.

    Args:
        category: Root cause category (e.g. 'infrastructure', 'database', 'deployment').

    Returns:
        Escalation contacts and on-call channels.
    """
    escalation_map = {
        "infrastructure": ["#infra-oncall", "infra-team@company.com"],
        "database": ["#data-platform-oncall", "dba@company.com"],
        "deployment": ["#sre-oncall", "#releases"],
        "traffic": ["#sre-oncall", "networking-team@company.com"],
        "code": ["#sre-oncall", "#engineering-oncall"],
        "config": ["#sre-oncall", "platform-team@company.com"],
        "external": ["#sre-oncall", "vendor-escalation@company.com"],
    }
    contacts = escalation_map.get(category.lower(), ["#sre-oncall"])
    return f"Escalation for '{category}': {', '.join(contacts)}"


# ---------------------------------------------------------------------------
# LLM factory — resolves configured provider or falls back to MockLLM
# ---------------------------------------------------------------------------

def _build_llama_llm():
    """Instantiate the best available LlamaIndex LLM from configured API keys."""
    anthropic_key = settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
    openai_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    gemini_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")

    if anthropic_key:
        try:
            from llama_index.llms.anthropic import Anthropic  # type: ignore[import-untyped]
            return Anthropic(model="claude-3-5-haiku-20241022", api_key=anthropic_key, max_tokens=2048)
        except Exception:
            pass

    if openai_key:
        try:
            from llama_index.llms.openai import OpenAI  # type: ignore[import-untyped]
            return OpenAI(model="gpt-4o-mini", api_key=openai_key, max_tokens=2048)
        except Exception:
            pass

    if gemini_key:
        try:
            from llama_index.llms.gemini import Gemini  # type: ignore[import-untyped]
            return Gemini(model="models/gemini-2.0-flash", api_key=gemini_key)
        except Exception:
            pass

    logger.warning("No LLM API keys found for PlaybookRunbookAgent — using MockLLM (offline mode)")
    return MockLLM(max_tokens=512)


_SYSTEM_PROMPT = """You are the SRE Playbook & Runbook Agent.
Your task: given an incident root cause summary, find the most relevant remediation playbook(s)
from the knowledge base and extract concrete, ordered steps an on-call engineer can execute NOW.

Use the following tools:
1. search_playbooks(query) — find matching playbooks by keyword/description
2. get_playbook_steps(playbook_id) — retrieve full steps for a specific playbook
3. get_escalation_path(category) — get escalation contacts for a root cause category

Rules:
- Always call search_playbooks first with the root cause summary.
- Retrieve steps for the top 1-2 matching playbooks.
- If no playbook scores > 0, call get_escalation_path with the incident category.
- Synthesize a concise response listing: matched playbook(s), applicable steps, and escalation path.
- Never hallucinate steps not returned by the tools.
"""


class PlaybookRunbookAgent:
    """LlamaIndex ReActAgent specialist for playbook/runbook retrieval and step synthesis."""

    def __init__(self) -> None:
        self._tools = [
            FunctionTool.from_defaults(
                fn=search_playbooks,
                name="search_playbooks",
                description="Search SRE playbook knowledge base for remediation runbooks.",
            ),
            FunctionTool.from_defaults(
                fn=get_playbook_steps,
                name="get_playbook_steps",
                description="Retrieve full ordered remediation steps for a playbook by ID.",
            ),
            FunctionTool.from_defaults(
                fn=get_escalation_path,
                name="get_escalation_path",
                description="Get escalation contacts for a given root cause category.",
            ),
        ]

    def _build_agent(self) -> ReActAgent:
        return ReActAgent(
            tools=self._tools,
            llm=_build_llama_llm(),
            system_prompt=_SYSTEM_PROMPT,
            max_iterations=6,
            verbose=False,
        )

    async def execute(
        self,
        context: IncidentContext,
        correlation: CorrelationResult | None,
    ) -> PlaybookFindings:
        """Run the ReActAgent reasoning loop and return structured PlaybookFindings."""
        category = correlation.category.value if correlation else "unknown"
        root_cause = (
            correlation.root_cause_summary
            if correlation
            else f"Unknown incident in namespace={context.namespace or 'unknown'}"
        )
        query = (
            f"Incident: {root_cause}. "
            f"Category: {category}. "
            f"Service: {context.service_name or 'unknown'}. "
            f"Namespace: {context.namespace or 'unknown'}."
        )

        agent = self._build_agent()
        try:
            handler = agent.run(user_msg=query)
            agent_output = await asyncio.wait_for(handler, timeout=60.0)
            raw_response: str = agent_output.response if hasattr(agent_output, "response") else str(agent_output)
        except asyncio.TimeoutError:
            logger.warning("PlaybookRunbookAgent timed out; returning keyword-matched fallback")
            raw_response = self._keyword_fallback_response(root_cause, category)
        except Exception as exc:
            logger.error("PlaybookRunbookAgent failed: %s; returning keyword-matched fallback", exc)
            raw_response = self._keyword_fallback_response(root_cause, category)

        return self._parse_to_findings(raw_response, root_cause, category)

    def _keyword_fallback_response(self, root_cause: str, category: str) -> str:
        """Direct keyword match when the LLM agent is unavailable."""
        hits = search_playbooks(root_cause)
        escalation = get_escalation_path(category)
        return f"{hits}\n\n{escalation}"

    def _parse_to_findings(
        self,
        raw_response: str,
        root_cause: str,
        category: str,
    ) -> PlaybookFindings:
        """Convert agent free-text response into structured PlaybookFindings.

        This is a best-effort parse: IDs found in the response are used to retrieve
        full structured steps from the knowledge base directly, guaranteeing schema
        conformance regardless of what the LLM produced.
        """
        matched: list[PlaybookMatch] = []
        mentioned_ids = {
            pb["id"]
            for pb in _PLAYBOOKS
            if pb["id"].lower() in raw_response.lower()
        }

        for pb in _PLAYBOOKS:
            if pb["id"] not in mentioned_ids:
                continue
            score = _keyword_score(pb, root_cause)
            steps = [
                RunbookStep(
                    step_number=i + 1,
                    action=s["action"],
                    command=s.get("command"),
                    expected_outcome=s["expected_outcome"],
                    rollback=s.get("rollback"),
                )
                for i, s in enumerate(pb["steps"])
            ]
            matched.append(
                PlaybookMatch(
                    playbook_id=pb["id"],
                    title=pb["title"],
                    relevance_score=max(score, 0.5),  # agent chose it → at least 0.5
                    summary=pb["summary"],
                    applicable_steps=steps,
                )
            )

        # If agent didn't cite any IDs, fall back to keyword scoring
        if not matched:
            scored = sorted(
                ((pb, _keyword_score(pb, root_cause)) for pb in _PLAYBOOKS),
                key=lambda x: x[1],
                reverse=True,
            )
            best = [(pb, score) for pb, score in scored if score > 0][:2]
            for pb, score in best:
                steps = [
                    RunbookStep(
                        step_number=i + 1,
                        action=s["action"],
                        command=s.get("command"),
                        expected_outcome=s["expected_outcome"],
                        rollback=s.get("rollback"),
                    )
                    for i, s in enumerate(pb["steps"])
                ]
                matched.append(
                    PlaybookMatch(
                        playbook_id=pb["id"],
                        title=pb["title"],
                        relevance_score=score,
                        summary=pb["summary"],
                        applicable_steps=steps,
                    )
                )

        matched.sort(key=lambda m: m.relevance_score, reverse=True)
        recommended = matched[0] if matched else None

        escalation_contacts: list[str] = []
        for pb in _PLAYBOOKS:
            if any(pb["id"] == m.playbook_id for m in matched):
                escalation_contacts.extend(pb.get("escalation", []))
        if not escalation_contacts:
            escalation_contacts = [get_escalation_path(category)]

        return PlaybookFindings(
            incident_summary=root_cause,
            matched_playbooks=matched,
            recommended_runbook=recommended,
            escalation_path=list(dict.fromkeys(escalation_contacts)),  # dedupe, preserve order
            notes=[f"Agent reasoning summary: {raw_response[:500]}"] if raw_response else [],
        )
