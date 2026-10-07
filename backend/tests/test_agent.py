from app.agent.agent import build_agent
from app.agent.schemas import AgentDecision
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
                hypotheses=[f"Investigating {self.service} evidence"],
            )
        return AgentDecision(
            action="diagnose",
            service=self.service,
            diagnosis=f"Evidence for {self.service} was collected from five deterministic tools.",
            proposed_action="Review the evidence and decide whether an approved action is needed.",
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