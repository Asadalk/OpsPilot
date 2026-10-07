from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.schemas import ServiceDeployment, ServiceHealth, ServiceIncident, ServiceLog, ServiceMetric


class ServiceToolInput(BaseModel):
    service: str = Field(..., min_length=1)


class BoundedServiceToolInput(ServiceToolInput):
    limit: int = Field(default=20, ge=1, le=100)


class MetricsToolInput(BoundedServiceToolInput):
    metric_name: str | None = None


class LogsToolInput(BoundedServiceToolInput):
    query: str | None = None
    level: Literal["debug", "info", "warn", "error"] | None = None


class RunbookSearchInput(BaseModel):
    query: str = Field(..., min_length=1)
    service: str | None = None


class HealthToolResult(ServiceHealth):
    pass


class MetricsToolResult(BaseModel):
    service: str
    metrics: list[ServiceMetric]


class LogsToolResult(BaseModel):
    service: str
    logs: list[ServiceLog]


class DeploymentsToolResult(BaseModel):
    service: str
    deployments: list[ServiceDeployment]


class IncidentsToolResult(BaseModel):
    service: str
    incidents: list[ServiceIncident]


class RunbookMatch(BaseModel):
    title: str
    summary: str
    source: str


class RunbookSearchResult(BaseModel):
    query: str
    matches: list[RunbookMatch]
    status: Literal["not_implemented"]
    message: str