from app.db.repositories import TaskNotFoundError, TaskRepository, TaskRepositoryError
from app.models.schemas import Task, TaskCreate, TaskStatus


class TaskServiceError(Exception):
    pass


class TaskService:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def create_tasks(self, items: list[TaskCreate]) -> list[Task]:
        try:
            return self.repository.create_tasks(items)
        except TaskRepositoryError as exc:
            raise TaskServiceError("Could not save extracted tasks") from exc

    def list_tasks(self) -> list[Task]:
        try:
            return self.repository.list_tasks()
        except TaskRepositoryError as exc:
            raise TaskServiceError("Could not load tasks") from exc

    def update_task(self, task_id: int, status: TaskStatus) -> Task:
        try:
            return self.repository.update_task(task_id, status)
        except TaskNotFoundError as exc:
            raise KeyError("Task not found") from exc
        except TaskRepositoryError as exc:
            raise TaskServiceError("Could not update task") from exc

    def delete_task(self, task_id: int) -> dict[str, str]:
        try:
            self.repository.delete_task(task_id)
            return {"message": "Task deleted"}
        except TaskNotFoundError as exc:
            raise KeyError("Task not found") from exc
        except TaskRepositoryError as exc:
            raise TaskServiceError("Could not delete task") from exc