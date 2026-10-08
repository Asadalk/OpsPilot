from app.db.simulator import ServiceNotFoundError, SimulatorRepository, SimulatorRepositoryError


class SimulatorServiceError(Exception):
    pass


class SimulatorServiceNotFoundError(SimulatorServiceError):
    pass


class SimulatorService:
    def __init__(self, repository: SimulatorRepository):
        self.repository = repository

    def _read(self, operation, service_id: int):
        try:
            return operation(service_id)
        except ServiceNotFoundError as exc:
            raise SimulatorServiceNotFoundError from exc
        except SimulatorRepositoryError as exc:
            raise SimulatorServiceError from exc

    def health(self, service_id: int) -> dict:
        return self._read(self.repository.get_health, service_id)

    def metrics(self, service_id: int) -> list[dict]:
        return self._read(self.repository.get_metrics, service_id)

    def logs(self, service_id: int) -> list[dict]:
        return self._read(self.repository.get_logs, service_id)

    def deployments(self, service_id: int) -> list[dict]:
        return self._read(self.repository.get_deployments, service_id)

    def incidents(self, service_id: int) -> list[dict]:
        return self._read(self.repository.get_incidents, service_id)

    def all_incidents(self) -> list[dict]:
        try:
            return self.repository.list_incidents()
        except SimulatorRepositoryError as exc:
            raise SimulatorServiceError from exc
