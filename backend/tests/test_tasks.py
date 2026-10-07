from unittest.mock import patch

from app.api.routes import tasks as task_routes
from app.services.gemini import GeminiTimeout


def test_health(api):
    response = api("GET", "/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_extract_list_update_delete(api):
    item = {"task": "Prepare slides", "owner": "Lee", "deadline": "Thursday", "priority": "high"}
    with patch.object(task_routes.gemini, "extract_tasks", return_value=[item]):
        created = api("POST", "/extract", json={"text": "Lee prepares slides by Thursday"})
    assert created.status_code == 200
    task_id = created.json()[0]["id"]
    assert created.json()[0]["status"] == "todo"
    assert api("GET", "/tasks").json()[0]["task"] == "Prepare slides"
    updated = api("PATCH", f"/tasks/{task_id}", json={"status": "in_progress"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"
    assert api("DELETE", f"/tasks/{task_id}").status_code == 200
    assert api("GET", "/tasks").json() == []


def test_invalid_model_task_is_not_persisted(api):
    with patch.object(task_routes.gemini, "extract_tasks", return_value=[{"task": "Bad priority", "priority": "urgent"}]):
        response = api("POST", "/extract", json={"text": "do thing"})
    assert response.status_code == 502
    assert api("GET", "/tasks").json() == []


def test_gemini_timeout_is_returned_as_gateway_timeout(api):
    with patch.object(task_routes.gemini, "extract_tasks", side_effect=GeminiTimeout("Gemini request timed out")):
        response = api("POST", "/extract", json={"text": "Prepare a plan"})
    assert response.status_code == 504
    assert response.json()["detail"] == "Gemini request timed out"


def test_nonexistent_task_and_invalid_status(api):
    assert api("PATCH", "/tasks/888", json={"status": "done"}).status_code == 404
    assert api("DELETE", "/tasks/888").status_code == 404
    assert api("PATCH", "/tasks/1", json={"status": "blocked"}).status_code == 422


def test_empty_input(api):
    assert api("POST", "/extract", json={"text": "  "}).status_code == 422
