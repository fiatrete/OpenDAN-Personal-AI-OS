from fastapi import FastAPI
from response import *
from google_calendar.event import *

app = FastAPI(
    title="OpenDAN Schedule Assistant API",
    description="",
    version="0.1.0",
)


@app.get("/tasks", response_model=Response, summary="Get all the tasks", description="", tags=['TASK'])
async def tasks():
    return get_events()


class AddTaskParams(BaseModel):
    start_time: int
    end_time: int
    summary: Union[str, None] = None
    description: Union[str, None] = None


@app.post("/task/add", response_model=Response, summary="Add a task", description="", tags=['TASK'])
async def add_task(params: AddTaskParams):
    return add_event(params.start_time, params.end_time, params.summary, params.description)


@app.post(
    "/task/delete/{task_id}",
    response_model=Response,
    summary="Delete task with TaskId",
    description="",
    tags=['TASK']
)
async def delete_task(task_id: str):
    return delete_event(task_id)


@app.get(
    "/task/{task_id}",
    response_model=Response,
    summary="Get task details",
    description="",
    tags=['TASK']
)
async def get_task(task_id: str):
    return get_event(task_id)
