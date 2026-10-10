import asyncio
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.agent.provider import DecisionProvider, MalformedDecisionError
from app.agent.schemas import AgentFailure, AgentState, AgentToolCall, KnowledgeCitation
from app.approval.repository import ApprovalRepository
from app.approval.service import ApprovalService
from app.auth.schemas import UserPrincipal
from app.core.config import settings
from app.db.agent import AgentRepository, AgentRepositoryError
from app.db.simulator import SimulatorRepository
from app.db.simulator_actions import EXECUTABLE_ACTIONS
from app.policy.engine import PolicyEngine
from app.rag.repository import KnowledgeRepository
from app.reliability import backoff, error_category, is_transient_error
from app.tools.base import ToolResultError
from app.tools.registry import build_default_tools


MAX_TRANSIENT_ATTEMPTS = 2


class OpsAgent:
    def __init__(self, repository: AgentRepository, provider: DecisionProvider, tools: dict, knowledge_repository: KnowledgeRepository, simulator_repository: SimulatorRepository, policy_engine: PolicyEngine, approval_service: ApprovalService, max_steps: int = 8):
        self.repository = repository
        self.provider = provider
        self.tools = tools
        self.knowledge_repository = knowledge_repository
        self.simulator_repository = simulator_repository
        self.policy_engine = policy_engine
        self.approval_service = approval_service
        self.max_steps = max_steps
        self.tool_timeout_seconds = settings.tool_timeout_seconds
        self.retrieval_timeout_seconds = settings.retrieval_timeout_seconds
        self.llm_timeout_seconds = settings.llm_timeout_seconds

    async def investigate(self, user_request: str, principal: UserPrincipal | None = None) -> AgentState:
        principal = principal or UserPrincipal(username="internal-test", role="admin")
        state = AgentState(run_id=uuid4(), user_request=user_request)
        try:
            self.repository.create_run(state.run_id, user_request, principal.username)
        except Exception as exc:
            self._failure(state, self._database_category(exc), "The run could not be stored because the database is unavailable.")
            state.status = "failed"
            state.diagnosis = "Investigation could not start; database persistence failed. Escalate and retry after database recovery."
            return state

        retrieval_started = time.perf_counter()
        await self._retrieve_knowledge(state, user_request)
        try:
            self.repository.record_event(
                state.run_id, "retrieval", state.retrieval_status,
                duration_ms=max(0, int((time.perf_counter() - retrieval_started) * 1000)),
                details={"citation_count": len(state.knowledge), "mode": "hybrid"},
                error=next((failure.category for failure in reversed(state.failure_states)
                            if failure.category in {"retrieval_failure", "retrieval_timeout", "temporary_database_error"}
                            and not failure.resolved), None),
            )
        except Exception as exc:
            self._failure(state, self._database_category(exc), "Retrieval trace could not be persisted.")
            state.status = "failed"
            state.diagnosis = "Investigation stopped because its retrieval trace could not be stored. Escalate for review."
            self._complete_safely(state, principal.username)
            return state
        descriptions = [self._describe_tool(tool) for tool in self.tools.values() if tool.kind == "read"]
        try:
            for step in range(self.max_steps):
                decision = await self._decide(state, descriptions, initial=(step == 0))
                if decision is None:
                    state.status = "failed"
                    category = state.failure_states[-1].category
                    state.diagnosis = self._failure_diagnosis(category)
                    self._complete_safely(state, principal.username)
                    return state
                state.service = decision.service or state.service
                state.severity = decision.severity or state.severity
                if decision.hypotheses:
                    state.hypotheses = decision.hypotheses
                    state.hypothesis_history.append(decision.hypotheses)
                if decision.action == "diagnose":
                    if not decision.diagnosis or not decision.diagnosis.strip():
                        self._failure(state, "malformed_model_response", "The model returned a diagnosis action without a diagnosis.")
                        state.status = "failed"
                        state.escalation_required = True
                        state.diagnosis = "The model did not provide a diagnosis. No successful conclusion was recorded; escalate for review."
                        self._complete_safely(state, principal.username)
                        return state
                    diagnosis = self._cite_knowledge(decision.diagnosis, state)
                    unresolved_tool_failure = any(
                        not failure.resolved and failure.category in {
                            "tool_timeout", "tool_failure", "malformed_tool_result", "temporary_database_error"
                        }
                        for failure in state.failure_states
                    )
                    returned_empty_records = any("returned empty records" in warning for warning in state.warnings)
                    has_independent_observation = any(
                        call.success and call.result and not self._contains_empty_collection(call.result)
                        for call in state.tool_calls
                    )
                    missing_operational_data = returned_empty_records and not has_independent_observation
                    retrieval_unavailable = any(
                        not failure.resolved and failure.category in {
                            "retrieval_failure", "retrieval_timeout", "temporary_database_error"
                        }
                        for failure in state.failure_states
                    )
                    state.escalation_required = unresolved_tool_failure or missing_operational_data or retrieval_unavailable
                    unsafe_evidence = unresolved_tool_failure or missing_operational_data or retrieval_unavailable
                    if decision.proposed_action and not unsafe_evidence:
                        self.repository.record_event(
                            state.run_id, "action_proposed", "proposed",
                            tool=decision.proposed_action.action_type,
                            details=decision.proposed_action.model_dump(mode="json"),
                        )
                        environment = self._resolve_environment(decision.proposed_action.target, state.service)
                        policy_decision = self.policy_engine.evaluate(decision.proposed_action, principal, environment)
                        state.policy_decision = policy_decision
                        self.repository.record_event(
                            state.run_id, "policy", policy_decision.outcome,
                            tool=decision.proposed_action.action_type,
                            details={"decision": policy_decision.model_dump(mode="json")},
                        )
                        action_status = {
                            "allow": "allowed",
                            "deny": "denied",
                            "require_approval": "approval_required",
                        }[policy_decision.outcome]
                        state.proposed_action = decision.proposed_action.model_copy(
                            update={"risk_level": policy_decision.risk_level, "status": action_status}
                        )
                        executable = state.proposed_action.action_type in EXECUTABLE_ACTIONS
                        if policy_decision.outcome == "require_approval" or (
                                policy_decision.outcome == "allow" and executable):
                            # Every simulator write goes through one recorded decision path.
                            state.approval = self.approval_service.repository.create_pending(
                                state.run_id, state.proposed_action, principal.username,
                                policy_decision.model_dump(mode="json"),
                            )
                            state.diagnosis = self._with_uncertainty(diagnosis, state)
                            state.status = "paused"
                            self._complete_safely(state, principal.username, audit_action=False)
                            if policy_decision.outcome == "allow":
                                state.approval = self.approval_service.execute_allowed(state.approval.id, principal)
                                state.status = "completed"
                            return state
                    elif decision.proposed_action and unsafe_evidence:
                        state.warnings.append("An action proposal was withheld because required tool evidence is incomplete.")
                        self.repository.record_event(
                            state.run_id, "action_withheld", "withheld",
                            tool=decision.proposed_action.action_type,
                            error="required_tool_evidence_incomplete",
                        )
                    state.diagnosis = self._with_uncertainty(diagnosis, state)
                    state.status = "failed" if state.escalation_required else "completed"
                    self._complete_safely(state, principal.username)
                    return state

                if (not decision.tool_name or decision.tool_name not in self.tools
                        or self.tools[decision.tool_name].kind != "read"):
                    self._failure(state, "malformed_model_response", "The model selected an unknown or non-read-only tool; no tool was run.")
                    state.status = "failed"
                    state.diagnosis = "Investigation stopped because the model returned an invalid tool selection. Escalate for review."
                    self._complete_safely(state, principal.username)
                    return state
                state.service = decision.arguments.get("service", state.service)
                persisted = await self._execute_tool(state, decision.tool_name, decision.arguments, principal.username)
                if not persisted:
                    state.status = "failed"
                    state.diagnosis = "Investigation stopped because the database could not persist tool evidence. Escalate; the recorded evidence may be incomplete."
                    self._complete_safely(state, principal.username)
                    return state

            state.status = "failed"
            self._failure(state, "step_limit", "The investigation reached its configured tool-step limit.")
            state.diagnosis = "Investigation reached its step limit without a supported conclusion. Escalate for human investigation."
            self._complete_safely(state, principal.username)
            return state
        except Exception as exc:
            self._failure(state, self._database_category(exc) if isinstance(exc, AgentRepositoryError) else "agent_failure",
                          "An internal investigation step failed; no successful conclusion was recorded.")
            state.status = "failed"
            state.diagnosis = "Investigation stopped after an internal failure. The result is uncertain and requires escalation."
            self._complete_safely(state, principal.username)
            return state

    async def _retrieve_knowledge(self, state: AgentState, query: str) -> None:
        last_error: Exception | None = None
        for attempt in range(1, MAX_TRANSIENT_ATTEMPTS + 1):
            try:
                rows = await asyncio.wait_for(
                    asyncio.to_thread(self.knowledge_repository.search, query, top_k=3),
                    timeout=self.retrieval_timeout_seconds,
                )
                state.knowledge = [KnowledgeCitation.model_validate(row) for row in rows]
                if attempt > 1:
                    self._failure(state, "temporary_database_error", "Knowledge retrieval recovered after a transient failure.",
                                  retryable=True, attempts=attempt, resolved=True)
                if state.knowledge:
                    state.retrieval_status = "ok"
                else:
                    state.retrieval_status = "empty"
                    self._failure(state, "retrieval_empty",
                                  "No knowledge chunks were returned; this does not mean relevant knowledge does not exist.")
                    state.warnings.append("Knowledge retrieval returned no matches; absence of retrieved knowledge is not evidence that relevant guidance does not exist.")
                state.evidence.append({"knowledge": [citation.model_dump(mode="json") for citation in state.knowledge],
                                       "retrieval_status": state.retrieval_status})
                return
            except Exception as exc:
                last_error = exc
                retryable = is_transient_error(exc)
                if retryable and attempt < MAX_TRANSIENT_ATTEMPTS:
                    await backoff(attempt)
                    continue
                break
        state.retrieval_status = "failed"
        category = error_category(last_error or RuntimeError(), operation="retrieval")
        self._failure(state, category,
                      "Knowledge retrieval failed; the investigation will continue without assuming that no guidance exists.",
                      retryable=is_transient_error(last_error) if last_error else False,
                      attempts=attempt)
        state.warnings.append("Knowledge retrieval failed; relevant guidance may exist and was not available to this run.")
        state.evidence.append({"retrieval_status": "failed", "error": category})

    async def _decide(self, state: AgentState, descriptions: list[dict[str, Any]], *, initial: bool = False):
        last_error: Exception | None = None
        decision_started = time.perf_counter()
        for attempt in range(1, MAX_TRANSIENT_ATTEMPTS + 1):
            try:
                decision = await asyncio.wait_for(
                    self.provider.decide(state, descriptions),
                    timeout=self.llm_timeout_seconds + getattr(self.provider, "max_wait_seconds", 0),
                )
            except Exception as exc:
                last_error = exc
                retryable = is_transient_error(exc)
                if retryable and attempt < MAX_TRANSIENT_ATTEMPTS:
                    await backoff(attempt, exc)
                    continue
                break
            if attempt > 1:
                self._failure(state, error_category(last_error or TimeoutError(), operation="llm"),
                              "The model call recovered after a transient failure.", retryable=True,
                              attempts=attempt, resolved=True)
            stage = "diagnosis" if decision.action == "diagnose" else ("classify" if initial else "planning")
            self.repository.record_event(
                state.run_id, stage, "completed",
                duration_ms=max(0, int((time.perf_counter() - decision_started) * 1000)),
                model=getattr(self.provider, "model", None), tool=decision.tool_name,
                details={"decision_action": decision.action, "service": decision.service,
                         "attempts": attempt,
                         # Provider-reported token counts; absent for scripted providers.
                         **(getattr(self.provider, "last_usage", None) or {})},
            )
            return decision
        category = "malformed_model_response" if isinstance(last_error, MalformedDecisionError) else error_category(last_error or RuntimeError(), operation="llm")
        self._failure(state, category,
                      "The model could not provide a valid decision; no diagnosis or action was inferred.",
                      retryable=is_transient_error(last_error) if last_error else False,
                      attempts=attempt)
        self.repository.record_event(
            state.run_id, "classify" if initial else "decision", "failed",
            duration_ms=max(0, int((time.perf_counter() - decision_started) * 1000)),
            model=getattr(self.provider, "model", None), error=category,
            # Provider error text (e.g. "429 RESOURCE_EXHAUSTED") explains the failure in the trace.
            details={"attempts": attempt,
                     **({"reason": f"{type(last_error).__name__}: {str(last_error)[:200]}"} if last_error else {})},
        )
        return None

    async def _execute_tool(self, state: AgentState, tool_name: str, arguments: dict[str, Any], actor: str) -> bool:
        tool = self.tools[tool_name]
        last_failure: AgentFailure | None = None
        for attempt in range(1, MAX_TRANSIENT_ATTEMPTS + 1):
            start_time = datetime.now(timezone.utc)
            try:
                result_model = await asyncio.wait_for(
                    asyncio.to_thread(tool.run, arguments), timeout=self.tool_timeout_seconds
                )
                result = result_model.model_dump(mode="json")
            except Exception as exc:
                category = "malformed_tool_result" if isinstance(exc, ToolResultError) else error_category(exc, operation="tool")
                retryable = is_transient_error(exc)
                failure_result = {"status": "error", "category": category,
                                  "message": "Tool timed out." if category == "tool_timeout" else "Tool returned no usable observation."}
                event = AgentToolCall(
                    call_index=len(state.tool_calls), tool=tool_name, arguments=arguments,
                    start_time=start_time, end_time=datetime.now(timezone.utc), result=failure_result,
                    success=False, error=failure_result["message"],
                )
                state.tool_calls.append(event)
                state.tool_results.append({"tool": tool_name, "result": failure_result})
                state.evidence.append({"tool_failure": {"tool": tool_name, **failure_result}})
                last_failure = AgentFailure(category=category, message=failure_result["message"],
                                            retryable=retryable, attempts=attempt)
                state.failure_states.append(last_failure)
                if not self._persist_tool_event(state, event, actor):
                    return False
                if retryable and attempt < MAX_TRANSIENT_ATTEMPTS:
                    await backoff(attempt)
                    continue
                state.warnings.append(f"Tool {tool_name} failed; the missing observation is not evidence of health.")
                return True

            event = AgentToolCall(
                call_index=len(state.tool_calls), tool=tool_name, arguments=arguments,
                start_time=start_time, end_time=datetime.now(timezone.utc), result=result,
                success=True,
            )
            state.tool_calls.append(event)
            state.tool_results.append({"tool": tool_name, "result": result})
            state.evidence.append({"tool": tool_name, "result": result})
            if last_failure:
                last_failure.resolved = True
                last_failure.message = "A transient tool failure recovered on retry."
                state.evidence.append({"failure_resolution": {
                    "category": last_failure.category, "resolved": True,
                    "message": last_failure.message, "attempts": attempt,
                }})
            if self._contains_empty_collection(result):
                warning = f"Tool {tool_name} returned empty records; no matching data does not establish healthy state."
                state.warnings.append(warning)
                state.evidence.append({"evidence_warning": warning})
            return self._persist_tool_event(state, event, actor)
        return True

    def _persist_tool_event(self, state: AgentState, event: AgentToolCall, actor: str) -> bool:
        try:
            self.repository.record_tool_call(
                state.run_id, event.call_index, event.tool, event.arguments,
                event.start_time, event.end_time, event.result, event.success, event.error, actor,
            )
            return True
        except Exception as exc:
            self._failure(state, self._database_category(exc),
                          "Tool evidence could not be persisted; investigation stopped.")
            return False

    def _complete_safely(self, state: AgentState, actor: str, audit_action: bool = True) -> None:
        try:
            self.repository.complete_run(
                state.run_id, state.service, state.severity, state.evidence,
                [hypothesis.model_dump(mode="json") for hypothesis in state.hypotheses],
                [[hypothesis.model_dump(mode="json") for hypothesis in group] for group in state.hypothesis_history],
                [citation.model_dump(mode="json") for citation in state.knowledge],
                state.proposed_action.model_dump(mode="json") if state.proposed_action else None,
                state.policy_decision.model_dump(mode="json") if state.policy_decision else None,
                state.diagnosis, state.proposed_action, state.status, actor, audit_action,
            )
        except Exception as exc:
            state.status = "failed"
            self._failure(state, self._database_category(exc),
                          "The final run state could not be persisted; the response may not match durable state.")
            state.diagnosis = "Investigation result could not be safely recorded. Treat it as uncertain and escalate."

    @staticmethod
    def _failure(state: AgentState, category: str, message: str, *, retryable: bool = False,
                 attempts: int = 1, resolved: bool = False) -> AgentFailure:
        failure = AgentFailure(category=category, message=message, retryable=retryable,
                               attempts=attempts, resolved=resolved)
        state.failure_states.append(failure)
        state.evidence.append({"failure": failure.model_dump(mode="json")})
        return failure

    @staticmethod
    def _database_category(error: BaseException) -> str:
        category = error_category(error, operation="database")
        return category if category == "temporary_database_error" else "database_failure"

    @staticmethod
    def _failure_diagnosis(category: str) -> str:
        if category == "llm_timeout":
            return "The decision model timed out after a bounded retry. No diagnosis was produced; escalate or retry later."
        if category == "malformed_model_response":
            return "The decision model returned malformed data. No diagnosis was produced; escalate for review."
        return "The decision model failed after a bounded attempt. No diagnosis was produced; escalate for review."

    @staticmethod
    def _with_uncertainty(diagnosis: str | None, state: AgentState) -> str:
        unresolved = [failure for failure in state.failure_states if not failure.resolved]
        if not unresolved and not state.warnings:
            return diagnosis or "No diagnosis was returned; the incident remains uncertain."
        reasons = list(dict.fromkeys([failure.category for failure in unresolved] + state.warnings))
        text = diagnosis or "Available evidence does not support a definitive diagnosis."
        return (
            f"Unverified model output: {text}\n\n"
            f"Uncertainty: {'; '.join(reasons)} Missing or unavailable evidence is not evidence of healthy state."
        )

    @staticmethod
    def _contains_empty_collection(value: Any) -> bool:
        if isinstance(value, dict):
            return any((isinstance(item, list) and not item) or OpsAgent._contains_empty_collection(item)
                       for item in value.values())
        if isinstance(value, list):
            return any(OpsAgent._contains_empty_collection(item) for item in value)
        return False

    @staticmethod
    def _describe_tool(tool) -> dict[str, Any]:
        """Compact tool description for the prompt: argument -> "type, required|optional[: help]"."""
        arguments = {}
        for name, field in tool.input_schema.model_fields.items():
            annotation = field.annotation
            kind = annotation.__name__ if isinstance(annotation, type) else str(annotation).replace("typing.", "")
            text = f"{kind}, {'required' if field.is_required() else 'optional'}"
            arguments[name] = f"{text}: {field.description}" if field.description else text
        return {"name": tool.name, "description": tool.description, "kind": tool.kind, "arguments": arguments}

    @staticmethod
    def _cite_knowledge(diagnosis: str | None, state: AgentState) -> str | None:
        if not diagnosis or not state.knowledge or "Sources:" in diagnosis:
            return diagnosis
        sources = "\n".join(
            f"[{index}] {citation.source}"
            for index, citation in enumerate(state.knowledge, start=1)
        )
        return f"{diagnosis}\n\nSources:\n{sources}"

    def _resolve_environment(self, target: str, service: str | None) -> str:
        candidate = target.split("@", 1)[0] or service
        if candidate:
            try:
                return self.simulator_repository.get_health(self.simulator_repository.get_service_id(candidate))["environment"]
            except Exception:
                pass
        return "production"


def build_agent(database_url: str, provider: DecisionProvider) -> OpsAgent:
    knowledge_repository = KnowledgeRepository(database_url)
    simulator_repository = SimulatorRepository(database_url)
    agent_repository = AgentRepository(database_url)
    approval_service = ApprovalService(ApprovalRepository(database_url))
    return OpsAgent(agent_repository, provider, build_default_tools(database_url), knowledge_repository,
                    simulator_repository, PolicyEngine(), approval_service)
