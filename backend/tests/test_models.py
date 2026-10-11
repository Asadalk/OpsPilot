import pytest
from pydantic import ValidationError

from app.models.schemas import ExtractRequest, ExtractedTask, TaskUpdateRequest


def test_valid_task_model():
    task = ExtractedTask.model_validate({"task": "Send report", "owner": "Ari", "deadline": "Friday", "priority": "high"})
    assert task.task == "Send report"


def test_invalid_priority_is_rejected():
    with pytest.raises(ValidationError):
        ExtractedTask.model_validate({"task": "Send report", "priority": "urgent"})


def test_blank_model_task_is_rejected():
    with pytest.raises(ValidationError):
        ExtractedTask.model_validate({"task": "   "})


def test_invalid_status_is_rejected():
    with pytest.raises(ValidationError):
        TaskUpdateRequest(status="blocked")


def test_empty_extraction_input_is_rejected():
    with pytest.raises(ValidationError):
        ExtractRequest(text="  ")
