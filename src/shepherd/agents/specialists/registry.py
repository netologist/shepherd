"""Specialist registry with dynamic alias normalization and third-party plugin support."""

from typing import Any
import re
from shepherd.agents.specialists.base import BaseSpecialist
from shepherd.agents.specialists.metrics import MetricsSpecialist
from shepherd.agents.specialists.traces import TracesSpecialist
from shepherd.agents.specialists.kubernetes import KubernetesSpecialist
from shepherd.agents.specialists.troubleshoot import TroubleshootSpecialist


# Alias mapping for fuzzy LLM naming normalization
SPECIALIST_ALIASES: dict[str, str] = {
    "k8s": "kubernetes",
    "k8s-agent": "kubernetes",
    "kubernetes-specialist": "kubernetes",
    "kube": "kubernetes",
    "metric": "metrics",
    "metrics-specialist": "metrics",
    "prom": "metrics",
    "prometheus": "metrics",
    "trace": "traces",
    "traces-specialist": "traces",
    "jaeger": "traces",
    "otel": "traces",
    "troubleshoot-specialist": "troubleshoot",
    "troubleshooting": "troubleshoot",
    "precheck": "troubleshoot",
    "static-checks": "troubleshoot",
}


class SpecialistRegistry:
    """Central registry discovering and dispatching native and external specialists."""

    def __init__(self):
        self._specialists: dict[str, BaseSpecialist] = {}
        self._register_default_specialists()

    def _register_default_specialists(self) -> None:
        self.register(MetricsSpecialist())
        self.register(TracesSpecialist())
        self.register(KubernetesSpecialist())
        self.register(TroubleshootSpecialist())

    def register(self, specialist: BaseSpecialist) -> None:
        self._specialists[specialist.domain.lower()] = specialist

    def normalize_name(self, raw_name: str) -> str:
        """Normalizes fuzzy or free-form LLM specialist names to canonical keys."""
        cleaned = raw_name.strip().lower().replace("_", "-").replace(" ", "-")
        # Direct alias check
        if cleaned in SPECIALIST_ALIASES:
            return SPECIALIST_ALIASES[cleaned]
        # Direct domain check
        if cleaned in self._specialists:
            return cleaned
        # Substring matching
        for alias, canonical in SPECIALIST_ALIASES.items():
            if alias in cleaned:
                return canonical
        for domain in self._specialists.keys():
            if domain in cleaned:
                return domain
        return cleaned

    def get_specialist(self, domain_or_alias: str) -> BaseSpecialist | None:
        canonical = self.normalize_name(domain_or_alias)
        return self._specialists.get(canonical)

    def list_domains(self) -> list[str]:
        return list(self._specialists.keys())


specialist_registry = SpecialistRegistry()
