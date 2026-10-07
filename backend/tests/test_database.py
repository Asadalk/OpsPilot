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
        version = connection.execute("SELECT version FROM schema_migrations").fetchone()["version"]
    assert version == "001_initial_tasks.sql"
