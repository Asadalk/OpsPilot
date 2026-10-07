from typing import Any, Literal

from pydantic import BaseModel, Field

ActionType = Literal[
    "create_incident",
    "update_incident",
    "create_github_issue",
    "generate_report",
    "restart_service",
    "rollback_deployment",
    "delete_data",
]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ActionStatus = Literal["proposed", "allowed", "denied", "approval_required", "executed"]
VerificationStatus = Literal["SUCCESS", "FAILED", "INCONCLUSIVE"]


class SimulatorSnapshot(BaseModel):
    service: str
    state: Literal["healthy", "degraded", "failed"]
    metrics: dict[str, float]
    latest_deployment: dict[str, str] | None = None


class ActionAttempt(BaseModel):
    attempt: int = Field(..., ge=1, le=2)
    before: SimulatorSnapshot
    execution: dict[str, Any]
    after: SimulatorSnapshot
    verification: VerificationStatus
    reason: str
    reinvestigation: SimulatorSnapshot | None = None


class ActionVerification(BaseModel):
    status: VerificationStatus
    reason: str
    attempt_count: int = Field(..., ge=0, le=2)
    max_automatic_attempts: Literal[2] = 2
    escalated: bool
    attempts: list[ActionAttempt]


class SimulatorActionResult(BaseModel):
    status: Literal["simulated"] = "simulated"
    action_type: ActionType
    target: str
    pre_action_state: SimulatorSnapshot | None = None
    post_action_state: SimulatorSnapshot | None = None
    verification: ActionVerification
    resolved_incident_ids: list[int]
    message: str


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
