import psycopg

from app.db.database import get_connection


class SimulatorRepositoryError(Exception):
    pass


class ServiceNotFoundError(SimulatorRepositoryError):
    pass


class SimulatorRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def _ensure_service(self, connection: psycopg.Connection, service_id: int) -> None:
        if connection.execute("SELECT 1 FROM services WHERE id = %s", (service_id,)).fetchone() is None:
            raise ServiceNotFoundError

    def get_health(self, service_id: int) -> dict:
        try:
            with get_connection(self.database_url) as connection:
                row = connection.execute(
                    "SELECT id AS service_id, name, environment, repository, current_state AS state FROM services WHERE id = %s",
                    (service_id,),
                ).fetchone()
            if row is None:
                raise ServiceNotFoundError
            return dict(row)
        except ServiceNotFoundError:
            raise
        except psycopg.Error as exc:
            raise SimulatorRepositoryError from exc

    def _list_for_service(self, service_id: int, query: str) -> list[dict]:
        try:
            with get_connection(self.database_url) as connection:
                self._ensure_service(connection, service_id)
                return [dict(row) for row in connection.execute(query, (service_id,)).fetchall()]
        except ServiceNotFoundError:
            raise
        except psycopg.Error as exc:
            raise SimulatorRepositoryError from exc

    def get_metrics(self, service_id: int) -> list[dict]:
        return self._list_for_service(
            service_id,
            "SELECT metrics.id, metrics.timestamp, services.name AS service, metrics.metric_name, metrics.value "
            "FROM metrics JOIN services ON services.id = metrics.service_id "
            "WHERE metrics.service_id = %s ORDER BY metrics.timestamp DESC",
        )

    def get_logs(self, service_id: int) -> list[dict]:
        return self._list_for_service(
            service_id,
            "SELECT logs.id, logs.timestamp, services.name AS service, logs.level, logs.message, logs.trace_id "
            "FROM logs JOIN services ON services.id = logs.service_id "
            "WHERE logs.service_id = %s ORDER BY logs.timestamp DESC",
        )

    def get_deployments(self, service_id: int) -> list[dict]:
        return self._list_for_service(
            service_id,
            "SELECT deployments.deployment_id, deployments.service_id, services.name AS service, deployments.version, "
            "deployments.deployed_at, deployments.author, deployments.status "
            "FROM deployments JOIN services ON services.id = deployments.service_id "
            "WHERE deployments.service_id = %s ORDER BY deployments.deployed_at DESC",
        )

    def get_incidents(self, service_id: int) -> list[dict]:
        return self._list_for_service(
            service_id,
            "SELECT incidents.id, incidents.title, incidents.severity, incidents.status, incidents.service_id, "
            "services.name AS service, incidents.created_at, incidents.updated_at "
            "FROM incidents JOIN services ON services.id = incidents.service_id "
            "WHERE incidents.service_id = %s ORDER BY incidents.created_at DESC",
        )