from app.db.database import get_connection, init_db
from app.db.repositories import TaskRepository
from app.models.schemas import TaskCreate


def test_repository_task_crud(database_path):
    init_db(database_path)
    with get_connection(database_path) as connection:
        connection.execute("TRUNCATE tasks RESTART IDENTITY")
    repository = TaskRepository(database_path)
    created = repository.create_tasks([TaskCreate(task="Review plan", owner="Mina", deadline="Monday")])
    assert created[0].task == "Review plan"
    assert repository.update_task(created[0].id, "done").status == "done"
    repository.delete_task(created[0].id)
    assert repository.list_tasks() == []


def test_initial_migration_is_recorded(database_path):
    init_db(database_path)
    with get_connection(database_path) as connection:
        versions = {row["version"] for row in connection.execute("SELECT version FROM schema_migrations")}
    assert versions == {
        "001_initial_tasks.sql",
        "002_operational_domain.sql",
        "003_ops_simulator.sql",
        "004_agent_runs.sql",
            "005_knowledge_vectors.sql",
            "006_agent_knowledge_citations.sql",
    }


def test_operational_domain_seed_is_queryable(database_path):
    init_db(database_path)
    with get_connection(database_path) as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            for table in ("services", "incidents", "deployments", "logs", "metrics")
        }
        incident = connection.execute(
            "SELECT incidents.title, services.name FROM incidents JOIN services ON services.id = incidents.service_id WHERE incidents.title = %s",
            ("Elevated order latency",),
        ).fetchone()
    assert counts["services"] >= 8
    assert counts["incidents"] >= 7
    assert counts["deployments"] >= 6
    assert counts["logs"] >= 8
    assert counts["metrics"] >= 8
    assert incident == {"title": "Elevated order latency", "name": "orders-api"}
