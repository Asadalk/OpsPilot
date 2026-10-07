from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Priority = Literal["high", "medium", "low"]
TaskStatus = Literal["todo", "in_progress", "done"]


class ExtractRequest(BaseModel):
    text: str = Field(..., min_length=1)

    @field_validator("text")
    @classmethod
    def reject_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Input text must not be empty")
        return value


class ExtractedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task: str = Field(..., min_length=1)
    owner: str = Field(default="Unknown")
    deadline: str = Field(default="Not specified")
    priority: Priority = "medium"

    @field_validator("task")
    @classmethod
    def reject_blank_task(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Task text must not be empty")
        return value

    @field_validator("owner")
    @classmethod
    def normalize_owner(cls, value: str) -> str:
        return value.strip() or "Unknown"

    @field_validator("deadline")
    @classmethod
    def normalize_deadline(cls, value: str) -> str:
        return value.strip() or "Not specified"


class TaskUpdateRequest(BaseModel):
    status: TaskStatus


class Task(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task: str
    owner: str
    deadline: str
    priority: Priority
    status: TaskStatus
    created_at: str


class TaskCreate(BaseModel):
    task: str = Field(..., min_length=1)
    owner: str = "Unknown"
    deadline: str = "Not specified"
    priority: Priority = "medium"


def normalize_task(item: dict[str, object]) -> TaskCreate:
    return TaskCreate.model_validate(ExtractedTask.model_validate(item).model_dump())


def now_iso() -> str:
    return datetime.utcnow().isoformat()