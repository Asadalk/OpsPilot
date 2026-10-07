from pathlib import Path

from app.rag.ingest import ingest_directory
from app.tools.base import ToolInputError
from app.tools.registry import build_default_tools


def test_operational_tools_are_standalone_and_structured(database_path):
    tools = build_default_tools(database_path)

    health = tools["get_service_health"].run({"service": "payments-api"})
    metrics = tools["get_metrics"].run({"service": "payments-api"})
    logs = tools["search_logs"].run({"service": "payments-api", "query": "database timeout"})
    deployments = tools["get_recent_deployments"].run({"service": "payments-api"})
    incidents = tools["get_incident_history"].run({"service": "payments-api"})

    assert health.state == "degraded"
    assert metrics.metrics[0].metric_name == "http_request_latency_ms"
    assert logs.logs[0].trace_id == "trace-payments-latency-001"
    assert deployments.deployments[0].version == "2026.10.07.14"
    assert any(incident.status == "resolved" for incident in incidents.incidents)


def test_tool_input_and_runbook_placeholder_errors_are_explicit(database_path):
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)
    tools = build_default_tools(database_path)

    try:
        tools["get_metrics"].run({"service": "payments-api", "limit": 0})
    except ToolInputError:
        pass
    else:
        raise AssertionError("invalid tool input should fail explicitly")

    runbooks = tools["search_runbooks"].run({"query": "database timeout"})
    assert runbooks.status == "ok"
    assert runbooks.matches
    assert runbooks.matches[0].source in {"runbooks/database-timeout.md", "runbooks/payment-latency.md"}