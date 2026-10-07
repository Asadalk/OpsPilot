from fastapi import APIRouter, HTTPException

from app.models.schemas import ExtractRequest, Task, TaskUpdateRequest, normalize_task
from app.services import gemini
from app.services.rag import retrieve
from app.services.tasks import TaskService, TaskServiceError


def build_task_router(task_service: TaskService) -> APIRouter:
    route = APIRouter()

    @route.post("/extract", response_model=list[Task])
    async def extract_tasks(payload: ExtractRequest) -> list[Task]:
        try:
            retrieved_guidelines = retrieve(payload.text)
            extracted = await gemini.extract_tasks(payload.text, retrieved_guidelines=retrieved_guidelines)
            validated = [normalize_task(item) for item in extracted]
        except gemini.GeminiTimeout as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except gemini.GeminiError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=502, detail="Gemini returned invalid task data") from exc
        try:
            return task_service.create_tasks(validated)
        except TaskServiceError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @route.get("/tasks", response_model=list[Task])
    async def get_tasks() -> list[Task]:
        try:
            return task_service.list_tasks()
        except TaskServiceError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @route.patch("/tasks/{task_id}", response_model=Task)
    async def patch_task(task_id: int, payload: TaskUpdateRequest) -> Task:
        try:
            return task_service.update_task(task_id, payload.status)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        except TaskServiceError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @route.delete("/tasks/{task_id}")
    async def remove_task(task_id: int) -> dict[str, str]:
        try:
            return task_service.delete_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        except TaskServiceError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return route