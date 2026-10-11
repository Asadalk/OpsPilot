"""Deterministic decision providers: no model, no network.

RuleBasedDecisionProvider runs inside the real OpsPilot pipeline (tools, policy, approval,
verification) but decides with fixed rules, so two runs give identical results. The rules
were written for the simulator and OpsBench worlds; its scores show the pipeline is
reproducible, not that rules beat a model.

MockDecisionProvider wraps it with switchable failure modes for offline tests, the
keyless demo (LLM_PROVIDER=mock), and failure injection.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Literal

from app.actions.schemas import ActionProposal
from app.agent.provider import MalformedDecisionError
from app.agent.schemas import AgentDecision, AgentState, Hypothesis

KEYWORD_SERVICES = [
    ("checkout", "checkout-api"), ("purchase", "checkout-api"), ("payment", "payments-api"), ("pay", "payments-api"),
    ("login", "auth-api"), ("auth", "auth-api"), ("email", "notification-api"), ("notification", "notification-api"),
    ("inventory", "inventory-api"), ("stock", "inventory-api"), ("order", "orders-api"), ("catalog", "catalog-api"),
]
EVIDENCE_TOOLS = ["get_service_health", "get_metrics", "search_logs", "get_recent_deployments"]


def target_service(request: str) -> str | None:
    named = re.findall(r"\b([a-z]+-api)\b", request.lower())
    if named:
        return named[0]
    lowered = request.lower()
    return next((service for keyword, service in KEYWORD_SERVICES if keyword in lowered), None)


EXPLICIT_REQUEST = re.compile(r"\b(restart|bounce|roll ?back)\b[^.]*?\b([a-z]+-api)\b")


class RuleBasedDecisionProvider:
    model = "rule-based"

    def __init__(self, obedient: bool = False):
        # obedient: propose exactly what the request asks for ("restart X"), like a naive
        # assistant. Used to test whether verification catches a wrong remediation.
        self.obedient = obedient

    async def decide(self, state: AgentState, _tool_descriptions: list[dict[str, Any]]) -> AgentDecision:
        primary = target_service(state.user_request)
        if primary is None:
            return self._diagnose("No service could be identified from the request; escalate.", None, primary)
        called = [(call.tool, call.arguments.get("service")) for call in state.tool_calls]
        for tool in EVIDENCE_TOOLS:
            if (tool, primary) not in called:
                return self._call(tool, primary)
        requested = EXPLICIT_REQUEST.search(state.user_request.lower()) if self.obedient else None
        if requested:
            action = "restart_service" if requested.group(1) in {"restart", "bounce"} else "rollback_deployment"
            return self._diagnose(f"Requested {action} on {requested.group(2)}.", (action, requested.group(2)), primary)
        text = self._observed_text(state, primary)
        upstream = re.search(r"\b([a-z]+-api) returned", text)
        if upstream and upstream.group(1) != primary:
            dependency = upstream.group(1)
            for tool in ("get_service_health", "search_logs"):
                if (tool, dependency) not in called:
                    return self._call(tool, dependency)
            dependency_text = self._observed_text(state, dependency)
            if re.search(r"oomkilled|exited|panic", dependency_text):
                return self._diagnose(f"{primary} fails because its upstream dependency {dependency} crashed.",
                                      ("restart_service", dependency), primary)
        if "pool" in text or "db_timeout" in text:
            return self._diagnose(f"{primary} database connection pool is exhausted.", ("restart_service", primary), primary)
        if "config_mismatch" in text:
            return self._diagnose(f"{primary} latest deployment carries a configuration mismatch.",
                                  ("rollback_deployment", primary), primary)
        if re.search(r"oomkilled|exited|panic", text):
            return self._diagnose(f"{primary} process crashed.", ("restart_service", primary), primary)
        if re.search(r"smtp|relay|econnrefused", text):
            return self._diagnose(f"{primary} fails because an external provider dependency is unavailable; "
                                  "no action on the service fixes it.", None, primary)
        return self._diagnose(f"Insufficient evidence for {primary}: no matching metrics or logs. Escalate.", None, primary)

    @staticmethod
    def _observed_text(state: AgentState, service: str) -> str:
        results = [call.result for call in state.tool_calls if call.success and call.arguments.get("service") == service]
        return json.dumps(results, default=str).lower()

    @staticmethod
    def _call(tool: str, service: str) -> AgentDecision:
        return AgentDecision(action="call_tool", tool_name=tool, arguments={"service": service}, service=service,
                             hypotheses=[Hypothesis(hypothesis=f"Gathering {tool} evidence for {service}", score=0.5)])

    @staticmethod
    def _diagnose(diagnosis: str, action: tuple[str, str] | None, service: str | None) -> AgentDecision:
        proposal = None
        if action:
            proposal = ActionProposal(action_type=action[0], target=action[1], reason=diagnosis, evidence=[],
                                      risk_level="LOW", status="proposed")
        return AgentDecision(action="diagnose", service=service, diagnosis=diagnosis, proposed_action=proposal,
                             hypotheses=[Hypothesis(hypothesis=diagnosis, score=0.7)])


MockMode = Literal["normal", "timeout", "malformed", "unavailable"]


class MockProviderUnavailable(ConnectionError):
    """A transient provider outage (classified like a network error, so it is retried once)."""


class MockDecisionProvider:
    """Offline stand-in for an LLM provider.

    normal       rule-based decisions
    timeout      never answers within the agent's timeout
    malformed    returns output that fails the decision contract
    unavailable  raises a transient connection error on every call
    """

    model = "mock"

    def __init__(self, mode: MockMode = "normal", obedient: bool = False):
        self.mode = mode
        self.rules = RuleBasedDecisionProvider(obedient=obedient)
        self.usage_records: list[dict[str, int | None]] = []
        self.last_usage = None

    async def decide(self, state: AgentState, tool_descriptions: list[dict[str, Any]]) -> AgentDecision:
        if self.mode == "timeout":
            await asyncio.sleep(3600)
        if self.mode == "malformed":
            raise MalformedDecisionError("Invalid decision fields: action")
        if self.mode == "unavailable":
            raise MockProviderUnavailable("mock provider unavailable")
        return await self.rules.decide(state, tool_descriptions)
