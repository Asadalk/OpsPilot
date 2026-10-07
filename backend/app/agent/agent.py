from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.agent.provider import DecisionProvider
from app.agent.schemas import AgentState, AgentToolCall
from app.db.agent import AgentRepository, AgentRepositoryError
from app.tools.base import ToolError
from app.tools.registry import build_default_tools


class OpsAgent:
    def __init__(self, repository: AgentRepository, provider: DecisionProvider, tools: dict, max_steps: int = 8):
        self.repository = repository
        self.provider = provider
        self.tools = tools
        self.max_steps = max_steps

    async def investigate(self, user_request: str) -> AgentState:
        state = AgentState(run_id=uuid4(), user_request=user_request)
        self.repository.create_run(state.run_id, user_request)
        descriptions = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema.model_json_schema(),
            }
            for tool in self.tools.values()
        ]
        try:
            for _ in range(self.max_steps):
                decision = await self.provider.decide(state, descriptions)
                state.service = decision.service or state.service
                state.severity = decision.severity or state.severity
                state.hypotheses = decision.hypotheses or state.hypotheses
                if decision.action == "diagnose":
                    state.diagnosis = decision.diagnosis
                    state.proposed_action = decision.proposed_action
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
            state.hypotheses,
            state.diagnosis,
            state.proposed_action,
            state.status,
        )


def build_agent(database_url: str, provider: DecisionProvider) -> OpsAgent:
    return OpsAgent(AgentRepository(database_url), provider, build_default_tools(database_url))