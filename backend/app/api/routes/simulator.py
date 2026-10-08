from fastapi import APIRouter, HTTPException

from app.models.schemas import ServiceDeployment, ServiceHealth, ServiceIncident, ServiceLog, ServiceMetric
from app.services.simulator import SimulatorService, SimulatorServiceError, SimulatorServiceNotFoundError


def build_simulator_router(simulator_service: SimulatorService) -> APIRouter:
    route = APIRouter(prefix="/services")

    def read(operation, service_id: int):
        try:
            return operation(service_id)
        except SimulatorServiceNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Service not found") from exc
        except SimulatorServiceError as exc:
            raise HTTPException(status_code=500, detail="Simulator data unavailable") from exc

    @route.get("/{service_id}/health", response_model=ServiceHealth)
    async def service_health(service_id: int) -> ServiceHealth:
        return read(simulator_service.health, service_id)

    @route.get("/{service_id}/metrics", response_model=list[ServiceMetric])
    async def service_metrics(service_id: int) -> list[ServiceMetric]:
        return read(simulator_service.metrics, service_id)

    @route.get("/{service_id}/logs", response_model=list[ServiceLog])
    async def service_logs(service_id: int) -> list[ServiceLog]:
        return read(simulator_service.logs, service_id)

    @route.get("/{service_id}/deployments", response_model=list[ServiceDeployment])
    async def service_deployments(service_id: int) -> list[ServiceDeployment]:
        return read(simulator_service.deployments, service_id)

    @route.get("/{service_id}/incidents", response_model=list[ServiceIncident])
    async def service_incidents(service_id: int) -> list[ServiceIncident]:
        return read(simulator_service.incidents, service_id)

    return route


def build_incidents_router(simulator_service: SimulatorService) -> APIRouter:
    route = APIRouter(prefix="/incidents")

    @route.get("")
    async def list_incidents():
        try:
            return simulator_service.all_incidents()
        except SimulatorServiceError as exc:
            raise HTTPException(status_code=500, detail="Simulator data unavailable") from exc

    return route
