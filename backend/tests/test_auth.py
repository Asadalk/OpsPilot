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
    assert protected.status_code == 500
