def test_token_issuance_and_protected_agent_route(api):
    unauthenticated = api("POST", "/agent/investigate", json={"request": "investigate payments"})
    assert unauthenticated.status_code == 401

    token_response = api("POST", "/auth/token", json={"username": "viewer", "password": "viewer"})
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]

    protected = api(
        "POST",
        "/agent/investigate",
        headers={"Authorization": f"Bearer {token}"},
        json={"request": "investigate payments"},
    )
    assert protected.status_code == 500