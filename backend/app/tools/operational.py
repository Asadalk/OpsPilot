from app.db.simulator import ServiceNotFoundError, SimulatorRepository, SimulatorRepositoryError
from app.tools.base import Tool, ToolExecutionError
from app.tools.schemas import (
    BoundedServiceToolInput,
    DeploymentsToolResult,
    HealthToolResult,
    IncidentsToolResult,
    LogsToolInput,
    LogsToolResult,
    MetricsToolInput,
    MetricsToolResult,
    RunbookSearchInput,
    RunbookSearchResult,
    ServiceToolInput,
)


class OperationalTool(Tool):
    def __init__(self, repository: SimulatorRepository):
        self.repository = repository

    def service_id(self, service: str) -> int:
        try:
            return self.repository.get_service_id(service)
        except ServiceNotFoundError as exc:
            raise ToolExecutionError(f"Service not found: {service}") from exc
        except SimulatorRepositoryError as exc:
            raise ToolExecutionError("Simulator database unavailable") from exc


class GetServiceHealth(OperationalTool):
    name = "get_service_health"
    description = "Read the current deterministic health state for a simulated service."
    input_schema = ServiceToolInput
    result_schema = HealthToolResult

    def execute(self, parameters: ServiceToolInput) -> HealthToolResult:
        return self.result_schema.model_validate(self.repository.get_health(self.service_id(parameters.service)))


class GetMetrics(OperationalTool):
    name = "get_metrics"
    description = "Read recent deterministic metrics for a simulated service."
    input_schema = MetricsToolInput
    result_schema = MetricsToolResult

    def execute(self, parameters: MetricsToolInput) -> MetricsToolResult:
        service_id = self.service_id(parameters.service)
        records = self.repository.get_metrics(service_id)
        if parameters.metric_name:
            records = [record for record in records if record["metric_name"] == parameters.metric_name]
        return self.result_schema(service=parameters.service, metrics=records[: parameters.limit])


class SearchLogs(OperationalTool):
    name = "search_logs"
    description = "Search bounded deterministic logs for a simulated service."
    input_schema = LogsToolInput
    result_schema = LogsToolResult

    def execute(self, parameters: LogsToolInput) -> LogsToolResult:
        service_id = self.service_id(parameters.service)
        records = self.repository.search_logs(service_id, parameters.query, parameters.level, parameters.limit)
        return self.result_schema(service=parameters.service, logs=records)


class GetRecentDeployments(OperationalTool):
    name = "get_recent_deployments"
    description = "Read the most recent deterministic deployments for a simulated service."
    input_schema = BoundedServiceToolInput
    result_schema = DeploymentsToolResult

    def execute(self, parameters: BoundedServiceToolInput) -> DeploymentsToolResult:
        records = self.repository.get_deployments(self.service_id(parameters.service), parameters.limit)
        return self.result_schema(service=parameters.service, deployments=records)


class GetIncidentHistory(OperationalTool):
    name = "get_incident_history"
    description = "Read bounded incident history for a simulated service."
    input_schema = BoundedServiceToolInput
    result_schema = IncidentsToolResult

    def execute(self, parameters: BoundedServiceToolInput) -> IncidentsToolResult:
        records = self.repository.get_incidents(self.service_id(parameters.service), parameters.limit)
        return self.result_schema(service=parameters.service, incidents=records)


class SearchRunbooks(Tool[RunbookSearchInput, RunbookSearchResult]):
    name = "search_runbooks"
    description = "Placeholder for deterministic runbook search; full retrieval is a later phase."
    input_schema = RunbookSearchInput
    result_schema = RunbookSearchResult

    def execute(self, parameters: RunbookSearchInput) -> RunbookSearchResult:
        return RunbookSearchResult(
            query=parameters.query,
            matches=[],
            status="not_implemented",
            message="Runbook search is not implemented in Phase 6.",
        )