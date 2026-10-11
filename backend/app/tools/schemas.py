from typing import Literal

from pydantic import BaseModel, Field

from app.models.schemas import ServiceDeployment, ServiceHealth, ServiceIncident, ServiceLog, ServiceMetric


class ServiceToolInput(BaseModel):
    service: str = Field(..., min_length=1)


class BoundedServiceToolInput(ServiceToolInput):
    limit: int = Field(default=20, ge=1, le=100)


class MetricsToolInput(BoundedServiceToolInput):
    metric_name: str | None = Field(default=None, description="Case-insensitive substring of the metric name, e.g. 'latency'.")


class LogsToolInput(BoundedServiceToolInput):
    query: str | None = Field(default=None, description="Case-insensitive substring of the log message.")
    level: Literal["debug", "info", "warn", "error"] | None = None


class RunbookSearchInput(BaseModel):
    query: str = Field(..., min_length=1)
    service: str | None = None
    mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"


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
    source: str
    document: str
    chunk: int
    similarity: float
    content: str
    retrieval_mode: Literal["semantic", "keyword", "hybrid"] | None = None
    semantic_similarity: float | None = None
    keyword_score: float | None = None


class RunbookSearchResult(BaseModel):
    query: str
    matches: list[RunbookMatch]
    status: Literal["ok", "empty"]
    message: str