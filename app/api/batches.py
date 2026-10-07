import asyncio
import datetime
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.api_keys import APIKey
from app.auth.middleware import get_authenticated_key
from app.providers.base import ChatMessage, ChatRequest
from app.queue.dlq import DLQItem, dlq_manager
from app.routing.router import router

batches_router = APIRouter(tags=["Batch Processing & DLQ"])


class BatchRequestItem(BaseModel):
    custom_id: str
    body: dict[str, Any]


class CreateBatchRequest(BaseModel):
    endpoint: str = "/v1/chat/completions"
    completion_window: str = "24h"
    requests: list[BatchRequestItem]
    metadata: dict[str, Any] = Field(default_factory=dict)


class BatchCounts(BaseModel):
    total: int = 0
    completed: int = 0
    failed: int = 0


class BatchJob(BaseModel):
    id: str
    object: str = "batch"
    endpoint: str
    status: str  # 'validating', 'in_progress', 'completed', 'failed', 'cancelled'
    created_at: int
    in_progress_at: int | None = None
    completed_at: int | None = None
    failed_at: int | None = None
    request_counts: BatchCounts = Field(default_factory=BatchCounts)
    results: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


# In-Memory Batch Jobs Store
_BATCH_JOBS: dict[str, BatchJob] = {}


async def _process_batch_job(batch_id: str):
    """Background worker executing batch items concurrently with rate limiting."""
    job = _BATCH_JOBS.get(batch_id)
    if not job or job.status != "validating":
        return

    job.status = "in_progress"
    job.in_progress_at = int(datetime.datetime.utcnow().timestamp())

    # Process each request with bounded concurrency
    sem = asyncio.Semaphore(5)

    async def _process_single(item: dict[str, Any]):
        async with sem:
            if job.status == "cancelled":
                return
            custom_id = item["custom_id"]
            body = item["body"]
            try:
                # Convert body to ChatRequest
                messages = [
                    ChatMessage(role=m["role"], content=m["content"])
                    for m in body.get("messages", [])
                ]
                llm_req = ChatRequest(
                    model=body.get("model", "auto"),
                    messages=messages,
                    temperature=body.get("temperature", 0.7),
                    max_tokens=body.get("max_tokens"),
                )
                providers = router.route(llm_req)
                if not providers:
                    raise RuntimeError("No providers available for batch request")
                response = await providers[0].chat(llm_req)
                job.results.append({
                    "custom_id": custom_id,
                    "response": response.model_dump(),
                    "status_code": 200,
                })
                job.request_counts.completed += 1
            except Exception as e:
                job.errors.append({
                    "custom_id": custom_id,
                    "error": str(e),
                    "status_code": 500,
                })
                job.request_counts.failed += 1

    # Execute all items concurrently
    tasks = [_process_single(item) for item in job.metadata.get("_raw_items", [])]
    await asyncio.gather(*tasks, return_exceptions=True)

    if job.status != "cancelled":
        job.status = "completed"
        job.completed_at = int(datetime.datetime.utcnow().timestamp())


# Batch Endpoints
@batches_router.post("/v1/batches", response_model=BatchJob)
async def create_batch(
    req: CreateBatchRequest,
    background_tasks: BackgroundTasks,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Creates an asynchronous batch job (OpenAI Batch API compatible)."""
    batch_id = f"batch_{uuid.uuid4().hex[:12]}"
    now_ts = int(datetime.datetime.utcnow().timestamp())

    job = BatchJob(
        id=batch_id,
        endpoint=req.endpoint,
        status="validating",
        created_at=now_ts,
        request_counts=BatchCounts(total=len(req.requests)),
        metadata={
            **req.metadata,
            "_raw_items": [r.model_dump() for r in req.requests],
        },
    )
    _BATCH_JOBS[batch_id] = job
    background_tasks.add_task(_process_batch_job, batch_id)
    return job


@batches_router.get("/v1/batches/{batch_id}", response_model=BatchJob)
async def get_batch(
    batch_id: str,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Retrieves status and results for a batch job."""
    job = _BATCH_JOBS.get(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    return job


@batches_router.get("/v1/batches", response_model=list[BatchJob])
async def list_batches(
    limit: int = 20,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Lists all batch jobs."""
    jobs = list(_BATCH_JOBS.values())
    return sorted(jobs, key=lambda x: x.created_at, reverse=True)[:limit]


@batches_router.post("/v1/batches/{batch_id}/cancel", response_model=BatchJob)
async def cancel_batch(
    batch_id: str,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Cancels an in-progress batch job."""
    job = _BATCH_JOBS.get(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    job.status = "cancelled"
    return job


# Dead Letter Queue Endpoints
@batches_router.get("/v1/dlq", response_model=list[DLQItem])
async def list_dlq_items(
    status: str | None = None,
    limit: int = 50,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Lists dead-lettered requests awaiting inspection or retry."""
    return dlq_manager.list_items(status=status, limit=limit)


@batches_router.post("/v1/dlq/{item_id}/replay")
async def replay_dlq_item(
    item_id: str,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Replays a failed request from the Dead Letter Queue through the smart router."""
    item = dlq_manager.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"DLQ item '{item_id}' not found")

    try:
        body = item.payload
        messages = [
            ChatMessage(role=m["role"], content=m["content"])
            for m in body.get("messages", [])
        ]
        llm_req = ChatRequest(
            model=body.get("model", "auto"),
            messages=messages,
            temperature=body.get("temperature", 0.7),
            max_tokens=body.get("max_tokens"),
        )
        providers = router.route(llm_req)
        if not providers:
            raise RuntimeError("No providers available for replay")
        response = await providers[0].chat(llm_req)
        dlq_manager.mark_replayed(item_id)
        return {
            "status": "success",
            "item_id": item_id,
            "response": response.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Replay failed: {e!s}")


@batches_router.delete("/v1/dlq/{item_id}")
async def dismiss_dlq_item(
    item_id: str,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Dismisses and permanently deletes an item from the Dead Letter Queue."""
    success = dlq_manager.dismiss(item_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"DLQ item '{item_id}' not found")
    return {"status": "dismissed", "item_id": item_id}
