import psycopg

from app.db.database import get_connection
from app.models.schemas import Task, TaskCreate, TaskStatus, now_iso


class TaskRepositoryError(Exception):
    pass


class TaskNotFoundError(TaskRepositoryError):
    pass


class TaskRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url

    def create_tasks(self, items: list[TaskCreate]) -> list[Task]:
        try:
            with get_connection(self.database_url) as connection:
                created = []
                for item in items:
                    cursor = connection.execute(
                        "INSERT INTO tasks (task, owner, deadline, priority, status, created_at) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
                        (item.task, item.owner, item.deadline, item.priority, "todo", now_iso()),
                    )
                    row = cursor.fetchone()
                    created.append(Task(**dict(row)))
                connection.commit()
                return created
        except psycopg.Error as exc:
            raise TaskRepositoryError from exc

    def list_tasks(self) -> list[Task]:
        try:
            with get_connection(self.database_url) as connection:
                rows = connection.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
            return [Task(**dict(row)) for row in rows]
        except psycopg.Error as exc:
            raise TaskRepositoryError from exc

    def update_task(self, task_id: int, status: TaskStatus) -> Task:
        try:
            with get_connection(self.database_url) as connection:
                cursor = connection.execute("UPDATE tasks SET status = %s WHERE id = %s", (status, task_id))
                if cursor.rowcount == 0:
                    raise TaskNotFoundError
                row = connection.execute("SELECT * FROM tasks WHERE id = %s", (task_id,)).fetchone()
                connection.commit()
            return Task(**dict(row))
        except TaskNotFoundError:
            raise
        except psycopg.Error as exc:
            raise TaskRepositoryError from exc

    def delete_task(self, task_id: int) -> None:
        try:
            with get_connection(self.database_url) as connection:
                cursor = connection.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                if cursor.rowcount == 0:
                    raise TaskNotFoundError
                connection.commit()
        except TaskNotFoundError:
            raise
        except psycopg.Error as exc:
            raise TaskRepositoryError from exc