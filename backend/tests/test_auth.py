from app.db.database import get_connection


def test_token_issuance_and_protected_agent_route(api):
    unauthenticated = api("POST", "/agent/investigate", json={"request": "investigate payments"})
    assert unauthenticated.status_code == 401

    token_response = api("POST", "/auth/token", json={"username": "viewer", "password": "viewer"})
    assert token_response.status_code == 200
    with get_connection() as connection:
        login_event = connection.execute(
            "SELECT actor, event_type, result FROM audit_events WHERE entity_type='user' AND entity_id='viewer' "
            "ORDER BY event_id DESC LIMIT 1"
        ).fetchone()
    assert login_event["actor"] == "viewer"
    assert login_event["event_type"] == "auth.login"
    assert login_event["result"]["status"] == "success"
    token = token_response.json()["access_token"]

    protected = api(
        "POST",
        "/agent/investigate",
        headers={"Authorization": f"Bearer {token}"},
        json={"request": "investigate payments"},
    )
    assert protected.status_code == 200
    assert protected.json()["status"] == "failed"
    assert protected.json()["failure_states"]
    assert "No diagnosis was produced" in protected.json()["diagnosis"]


def test_non_development_startup_refuses_default_secret_and_dev_accounts():
    import dataclasses

    import pytest

    from app.core.config import check_deployment_settings, settings

    dev = dataclasses.replace(settings, environment="development", jwt_secret="ops-pilot-development-secret-change-me")
    check_deployment_settings(dev)  # allowed locally
    with pytest.raises(RuntimeError, match="JWT_SECRET.*AUTH_USERS_JSON"):
        check_deployment_settings(dataclasses.replace(dev, environment="production"))
    strong = dataclasses.replace(dev, environment="production", jwt_secret="x" * 40,
                                 auth_users_json='{"alice":{"password":"a-long-unique-password","role":"admin"}}')
    check_deployment_settings(strong)
