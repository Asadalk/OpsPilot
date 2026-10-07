from app.db.database import init_db
from app.db.repositories import TaskRepository
from app.models.schemas import TaskCreate


def test_repository_task_crud(database_path):
    init_db(database_path)
    repository = TaskRepository(database_path)
    created = repository.create_tasks([TaskCreate(task="Review plan", owner="Mina", deadline="Monday")])
    assert created[0].task == "Review plan"
    assert repository.update_task(created[0].id, "done").status == "done"
    repository.delete_task(created[0].id)
    assert repository.list_tasks() == []
