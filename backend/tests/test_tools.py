from pathlib import Path

from app.rag.ingest import ingest_directory
from app.tools.base import ToolExecutionError, ToolInputError
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


def test_every_service_tool_fails_explicitly_for_an_unknown_service(database_path):
    tools = build_default_tools(database_path)
    for name in ("get_service_health", "get_metrics", "search_logs", "get_recent_deployments", "get_incident_history"):
        try:
            tools[name].run({"service": "no-such-service"})
        except ToolExecutionError as exc:
            assert "Service not found" in str(exc), name
        else:
            raise AssertionError(f"{name} should reject an unknown service")


def test_runbook_search_reports_empty_instead_of_unrelated_matches(database_path):
    ingest_directory(Path(__file__).resolve().parents[2] / "knowledge", database_path)
    runbooks = build_default_tools(database_path)["search_runbooks"].run({"query": "qwxzv plorth"})
    assert runbooks.status == "empty"
    assert runbooks.matches == []


def test_metric_filter_matches_a_substring_of_the_metric_name(database_path):
    metrics = build_default_tools(database_path)["get_metrics"].run({"service": "payments-api", "metric_name": "LATENCY"})
    assert metrics.metrics and all("latency" in record.metric_name for record in metrics.metrics)
