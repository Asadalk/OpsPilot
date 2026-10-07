from app.agent.agent import build_agent
from app.agent.schemas import AgentDecision, Hypothesis
from app.actions.schemas import ActionProposal
from pathlib import Path

from app.db.database import get_connection, init_db
from app.rag.ingest import ingest_directory


class ScriptedDecisionProvider:
    def __init__(self, service: str):
        self.service = service
        self.tools = [
            "get_service_health",
            "get_metrics",
            "search_logs",
            "get_recent_deployments",
            "get_incident_history",
        ]

    async def decide(self, state, _tool_descriptions):
        if len(state.tool_calls) < len(self.tools):
            return AgentDecision(
                action="call_tool",
                tool_name=self.tools[len(state.tool_calls)],
                arguments={"service": self.service},
                service=self.service,
                hypotheses=[
                    Hypothesis(
                        hypothesis=f"Investigating {self.service} evidence",
                        score=0.5,
                        supporting_evidence=[],
                        contradicting_evidence=[],
                    )
                ],
            )
        return AgentDecision(
            action="diagnose",
            service=self.service,
            diagnosis=f"Evidence for {self.service} was collected from five deterministic tools.",
            proposed_action=ActionProposal(
                action_type="generate_report",
                target=self.service,
                reason="Record the investigation for review.",
                evidence=[],
                risk_level="low",
                status="proposed",
            ),
        )


def test_agent_reconstructs_five_incident_investigations(database_path):
    init_db(database_path)
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)
    services = ["payments-api", "checkout-api", "notification-api", "inventory-api", "orders-api"]
    run_ids = []

    for service in services:
        agent = build_agent(database_path, ScriptedDecisionProvider(service))
        state = __import__("asyncio").run(agent.investigate(f"Why is {service} unhealthy?"))
        run_ids.append(state.run_id)
        assert state.status == "completed"
        assert state.service == service
        assert state.diagnosis
        assert len(state.tool_calls) == 5
        assert all(call.success for call in state.tool_calls)

    with get_connection(database_path) as connection:
        run_count = connection.execute(
            "SELECT COUNT(*) AS count FROM agent_runs WHERE run_id = ANY(%s)",
            ([str(run_id) for run_id in run_ids],),
        ).fetchone()["count"]
        call_rows = connection.execute(
            "SELECT tool, success FROM agent_tool_calls WHERE run_id = %s ORDER BY call_index",
            (run_ids[0],),
        ).fetchall()

    assert run_count == len(services)
    assert [row["tool"] for row in call_rows] == [
        "get_service_health",
        "get_metrics",
        "search_logs",
        "get_recent_deployments",
        "get_incident_history",
    ]
    assert all(row["success"] for row in call_rows)


class MisleadingEvidenceProvider:
    async def decide(self, state, _tool_descriptions):
        if len(state.tool_calls) == 0:
            return AgentDecision(
                action="call_tool",
                tool_name="search_logs",
                arguments={"service": "inventory-api"},
                service="inventory-api",
                hypotheses=[
                    Hypothesis(
                        hypothesis="inventory cache failure",
                        score=0.65,
                        supporting_evidence=[{"tool": "search_logs", "message": "cache timeout observed"}],
                        contradicting_evidence=[],
                    ),
                    Hypothesis(
                        hypothesis="auth dependency failure",
                        score=0.35,
                        supporting_evidence=[],
                        contradicting_evidence=[],
                    ),
                ],
            )
        if len(state.tool_calls) == 1:
            return AgentDecision(
                action="call_tool",
                tool_name="search_logs",
                arguments={"service": "auth-api"},
                service="inventory-api",
                hypotheses=[
                    Hypothesis(
                        hypothesis="inventory cache failure",
                        score=0.2,
                        supporting_evidence=[{"tool": "search_logs", "message": "cache timeout observed"}],
                        contradicting_evidence=[{"tool": "search_logs", "message": "token issuer unavailable"}],
                    ),
                    Hypothesis(
                        hypothesis="auth dependency failure",
                        score=0.9,
                        supporting_evidence=[{"tool": "search_logs", "message": "token issuer unavailable"}],
                        contradicting_evidence=[],
                    ),
                ],
            )
        return AgentDecision(
            action="diagnose",
            service="inventory-api",
            diagnosis="The initial cache log was misleading; the auth dependency failure explains the request failures.",
            hypotheses=[
                Hypothesis(
                    hypothesis="auth dependency failure",
                    score=0.9,
                    supporting_evidence=[{"tool": "search_logs", "service": "auth-api"}],
                    contradicting_evidence=[],
                ),
                Hypothesis(
                    hypothesis="inventory cache failure",
                    score=0.2,
                    supporting_evidence=[{"tool": "search_logs", "service": "inventory-api"}],
                    contradicting_evidence=[{"tool": "search_logs", "service": "auth-api"}],
                ),
            ],
        )


def test_ambiguous_incident_compares_hypotheses_before_diagnosis(database_path):
    init_db(database_path)
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)
    agent = build_agent(database_path, MisleadingEvidenceProvider())

    state = __import__("asyncio").run(agent.investigate("Why are inventory requests failing?"))

    assert state.status == "completed"
    assert [call.arguments["service"] for call in state.tool_calls] == ["inventory-api", "auth-api"]
    assert len(state.hypothesis_history) == 3
    assert state.hypothesis_history[0][0].hypothesis == "inventory cache failure"
    assert state.hypothesis_history[0][0].score > state.hypothesis_history[0][1].score
    assert state.hypotheses[0].hypothesis == "auth dependency failure"
    assert state.hypotheses[0].score > state.hypotheses[1].score
    assert "auth dependency failure" in (state.diagnosis or "")

    with get_connection(database_path) as connection:
        history = connection.execute(
            "SELECT hypothesis_history FROM agent_runs WHERE run_id = %s",
            (state.run_id,),
        ).fetchone()["hypothesis_history"]
    assert len(history) == 3