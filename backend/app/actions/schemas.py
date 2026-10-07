from typing import Any, Literal

from pydantic import BaseModel, Field

ActionType = Literal[
    "create_incident",
    "update_incident",
    "create_github_issue",
    "generate_report",
    "restart_service",
    "rollback_deployment",
]
RiskLevel = Literal["low", "medium", "high"]
ActionStatus = Literal["proposed"]


class ActionProposal(BaseModel):
    action_type: ActionType
    target: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    risk_level: RiskLevel
    status: ActionStatus = "proposed"


class ActionProposalInput(BaseModel):
    action_type: ActionType
    target: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    evidence: list[dict[str, Any]] = Field(default_factory=list)