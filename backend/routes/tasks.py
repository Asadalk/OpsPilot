from fastapi import APIRouter, HTTPException

from models import ExtractRequest, Task, TaskUpdateRequest, normalize_task
from services import gemini, task_service
from services.rag import retrieve

router = APIRouter()


@router.post("/extract", response_model=list[Task])
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
    return task_service.create_tasks(validated)


@router.get("/tasks", response_model=list[Task])
async def get_tasks() -> list[Task]:
    return task_service.list_tasks()


@router.patch("/tasks/{task_id}", response_model=Task)
async def patch_task(task_id: int, payload: TaskUpdateRequest) -> Task:
    return task_service.update_task(task_id, payload.status)


@router.delete("/tasks/{task_id}")
async def remove_task(task_id: int) -> dict[str, str]:
    return task_service.delete_task(task_id)
