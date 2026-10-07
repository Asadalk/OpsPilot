from app.db.database import get_connection


def service_id(database_path, name: str) -> int:
    with get_connection(database_path) as connection:
        return connection.execute("SELECT id FROM services WHERE name = %s", (name,)).fetchone()["id"]


def test_payments_latency_incident_can_be_investigated(api, database_path):
    payments_id = service_id(database_path, "payments-api")

    health = api("GET", f"/services/{payments_id}/health")
    metrics = api("GET", f"/services/{payments_id}/metrics")
    logs = api("GET", f"/services/{payments_id}/logs")
    deployments = api("GET", f"/services/{payments_id}/deployments")
    incidents = api("GET", f"/services/{payments_id}/incidents")

    assert health.status_code == 200
    assert health.json()["state"] == "degraded"
    assert any(metric["metric_name"] == "http_request_latency_ms" and metric["value"] > 1000 for metric in metrics.json())
    assert any("Database timeout" in log["message"] for log in logs.json())
    assert deployments.json()[0]["version"] == "2026.10.07.14"
    assert {incident["status"] for incident in incidents.json()} == {"investigating", "resolved"}


def test_simulator_scenarios_have_deterministic_service_states(api, database_path):
    expected = {
        "payments-api": "degraded",
        "checkout-api": "degraded",
        "auth-api": "failed",
        "inventory-api": "degraded",
        "notification-api": "failed",
    }
    for name, state in expected.items():
        response = api("GET", f"/services/{service_id(database_path, name)}/health")
        assert response.status_code == 200
        assert response.json()["state"] == state


def test_unknown_service_is_not_found(api):
    response = api("GET", "/services/999999/health")
    assert response.status_code == 404