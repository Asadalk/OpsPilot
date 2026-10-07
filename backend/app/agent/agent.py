from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.agent.provider import DecisionProvider
from app.agent.schemas import AgentState, AgentToolCall, KnowledgeCitation
from app.approval.repository import ApprovalRepository
from app.approval.service import ApprovalService
from app.auth.schemas import UserPrincipal
from app.db.agent import AgentRepository, AgentRepositoryError
from app.db.simulator import SimulatorRepository
from app.policy.engine import PolicyEngine
from app.rag.repository import KnowledgeRepository
from app.tools.base import ToolError
from app.tools.registry import build_default_tools


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

    async def investigate(self, user_request: str, principal: UserPrincipal | None = None) -> AgentState:
        principal = principal or UserPrincipal(username="internal-test", role="admin")
        state = AgentState(run_id=uuid4(), user_request=user_request)
        self.repository.create_run(state.run_id, user_request)
        state.knowledge = [
            KnowledgeCitation.model_validate(citation)
            for citation in self.knowledge_repository.search(user_request, top_k=3)
        ]
        state.evidence.append({"knowledge": [citation.model_dump(mode="json") for citation in state.knowledge]})
        descriptions = [
            {
                "name": tool.name,
                "description": tool.description,
                "kind": tool.kind,
                "input_schema": tool.input_schema.model_json_schema(),
            }
            for tool in self.tools.values()
        ]
        try:
            for _ in range(self.max_steps):
                decision = await self.provider.decide(state, descriptions)
                state.service = decision.service or state.service
                state.severity = decision.severity or state.severity
                if decision.hypotheses:
                    state.hypotheses = decision.hypotheses
                    state.hypothesis_history.append(decision.hypotheses)
                if decision.action == "diagnose":
                    state.diagnosis = self._cite_knowledge(decision.diagnosis, state)
                    if decision.proposed_action:
                        environment = self._resolve_environment(decision.proposed_action.target, state.service)
                        policy_decision = self.policy_engine.evaluate(decision.proposed_action, principal, environment)
                        state.policy_decision = policy_decision
                        action_status = {
                            "allow": "allowed",
                            "deny": "denied",
                            "require_approval": "approval_required",
                        }[policy_decision.outcome]
                        state.proposed_action = decision.proposed_action.model_copy(
                            update={"risk_level": policy_decision.risk_level, "status": action_status}
                        )
                        if policy_decision.outcome == "require_approval":
                            state.approval = self.approval_service.repository.create_pending(state.run_id, state.proposed_action)
                            state.proposed_action = state.proposed_action.model_copy(update={"status": "approval_required"})
                            state.status = "paused"
                            self._complete(state)
                            return state
                    state.status = "completed"
                    self._complete(state)
                    return state
                if not decision.tool_name or decision.tool_name not in self.tools:
                    raise ValueError(f"Unknown tool requested: {decision.tool_name}")
                state.service = decision.arguments.get("service", state.service)
                self._execute_tool(state, decision.tool_name, decision.arguments)
            state.status = "failed"
            state.diagnosis = "Investigation exceeded the maximum tool-step limit."
            self._complete(state)
            return state
        except Exception:
            state.status = "failed"
            self._complete(state)
            raise

    def _execute_tool(self, state: AgentState, tool_name: str, arguments: dict[str, Any]) -> None:
        start_time = datetime.now(timezone.utc)
        result: dict[str, Any] | None = None
        error: str | None = None
        success = False
        try:
            result_model = self.tools[tool_name].run(arguments)
            result = result_model.model_dump(mode="json")
            state.tool_results.append({"tool": tool_name, "result": result})
            state.evidence.append({"tool": tool_name, "result": result})
            success = True
        except ToolError as exc:
            error = str(exc)
        end_time = datetime.now(timezone.utc)
        event = AgentToolCall(
            call_index=len(state.tool_calls),
            tool=tool_name,
            arguments=arguments,
            start_time=start_time,
            end_time=end_time,
            result=result,
            success=success,
            error=error,
        )
        state.tool_calls.append(event)
        self.repository.record_tool_call(
            state.run_id,
            event.call_index,
            event.tool,
            event.arguments,
            event.start_time,
            event.end_time,
            event.result,
            event.success,
            event.error,
        )
        if not success:
            raise ToolError(error or "Tool failed")

    def _complete(self, state: AgentState) -> None:
        self.repository.complete_run(
            state.run_id,
            state.service,
            state.severity,
            state.evidence,
            [hypothesis.model_dump(mode="json") for hypothesis in state.hypotheses],
            [[hypothesis.model_dump(mode="json") for hypothesis in hypotheses] for hypotheses in state.hypothesis_history],
            [citation.model_dump(mode="json") for citation in state.knowledge],
            state.proposed_action.model_dump(mode="json") if state.proposed_action else None,
            state.policy_decision.model_dump(mode="json") if state.policy_decision else None,
            state.diagnosis,
            state.proposed_action,
            state.status,
        )

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
    return OpsAgent(agent_repository, provider, build_default_tools(database_url), knowledge_repository, simulator_repository, PolicyEngine(), approval_service)
