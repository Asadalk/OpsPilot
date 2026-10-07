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

    def get_service_id(self, service: str) -> int:
        try:
            with get_connection(self.database_url) as connection:
                row = connection.execute("SELECT id FROM services WHERE name = %s", (service,)).fetchone()
            if row is None:
                raise ServiceNotFoundError
            return row["id"]
        except ServiceNotFoundError:
            raise
        except psycopg.Error as exc:
            raise SimulatorRepositoryError from exc

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

    def search_logs(self, service_id: int, query: str | None, level: str | None, limit: int) -> list[dict]:
        try:
            with get_connection(self.database_url) as connection:
                self._ensure_service(connection, service_id)
                rows = connection.execute(
                    "SELECT logs.id, logs.timestamp, services.name AS service, logs.level, logs.message, logs.trace_id "
                    "FROM logs JOIN services ON services.id = logs.service_id "
                    "WHERE logs.service_id = %s "
                    "AND (CAST(%s AS TEXT) IS NULL OR logs.message ILIKE %s) "
                    "AND (CAST(%s AS TEXT) IS NULL OR logs.level = %s) "
                    "ORDER BY logs.timestamp DESC LIMIT %s",
                    (service_id, query, f"%{query}%" if query else None, level, level, limit),
                ).fetchall()
            return [dict(row) for row in rows]
        except ServiceNotFoundError:
            raise
        except psycopg.Error as exc:
            raise SimulatorRepositoryError from exc

    def get_logs(self, service_id: int) -> list[dict]:
        return self._list_for_service(
            service_id,
            "SELECT logs.id, logs.timestamp, services.name AS service, logs.level, logs.message, logs.trace_id "
            "FROM logs JOIN services ON services.id = logs.service_id "
            "WHERE logs.service_id = %s ORDER BY logs.timestamp DESC",
        )

    def get_deployments(self, service_id: int, limit: int = 20) -> list[dict]:
        return self._list_for_service(
            service_id,
            "SELECT deployments.deployment_id, deployments.service_id, services.name AS service, deployments.version, "
            "deployments.deployed_at, deployments.author, deployments.status "
            "FROM deployments JOIN services ON services.id = deployments.service_id "
            f"WHERE deployments.service_id = %s ORDER BY deployments.deployed_at DESC LIMIT {limit}",
        )

    def get_incidents(self, service_id: int, limit: int = 20) -> list[dict]:
        return self._list_for_service(
            service_id,
            "SELECT incidents.id, incidents.title, incidents.severity, incidents.status, incidents.service_id, "
            "services.name AS service, incidents.created_at, incidents.updated_at "
            "FROM incidents JOIN services ON services.id = incidents.service_id "
            f"WHERE incidents.service_id = %s ORDER BY incidents.created_at DESC LIMIT {limit}",
        )