import datetime
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth.api_keys import APIKey
from app.auth.middleware import get_authenticated_key
from app.evals.heuristics import ComprehensiveEvalReport, HeuristicEvaluator

feedback_router = APIRouter(prefix="/v1", tags=["Feedback & Evals"])


class FeedbackSubmission(BaseModel):
    request_id: str | None = None
    model: str | None = None
    rating: int = Field(..., ge=1, le=5, description="1 (poor) to 5 (excellent)")
    thumb: str | None = Field(None, description="'up' or 'down'")
    comment: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackRecord(FeedbackSubmission):
    id: str
    team_id: str | None = None
    created_at: str


class RunEvalRequest(BaseModel):
    text: str
    expect_json: bool = False
    required_json_keys: list[str] | None = None
    ground_truth_keywords: list[str] | None = None
    min_chars: int = 1
    max_chars: int = 50000


# In-Memory Feedback Store (Persisted to DB in production setup)
_FEEDBACK_STORE: list[FeedbackRecord] = []


@feedback_router.post("/feedback", response_model=FeedbackRecord)
async def submit_feedback(
    payload: FeedbackSubmission,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Submits end-user or developer feedback on an LLM completion."""
    record = FeedbackRecord(
        id=f"fb_{uuid.uuid4().hex[:10]}",
        team_id=api_key.team_id,
        created_at=datetime.datetime.utcnow().isoformat(),
        **payload.model_dump(),
    )
    _FEEDBACK_STORE.append(record)
    return record


@feedback_router.get("/feedback", response_model=list[FeedbackRecord])
async def list_feedback(
    team_id: str | None = None,
    model: str | None = None,
    min_rating: int | None = Query(None, ge=1, le=5),
    limit: int = 50,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Lists feedback records with filtering."""
    results = _FEEDBACK_STORE
    if team_id:
        results = [r for r in results if r.team_id == team_id]
    if model:
        results = [r for r in results if r.model == model]
    if min_rating is not None:
        results = [r for r in results if r.rating >= min_rating]

    return results[-limit:]


@feedback_router.get("/feedback/stats")
async def get_feedback_stats(
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Computes aggregate feedback metrics (CSAT, rating distribution)."""
    if not _FEEDBACK_STORE:
        return {
            "total_submissions": 0,
            "average_rating": 0.0,
            "thumbs_up_count": 0,
            "thumbs_down_count": 0,
            "csat_percentage": 0.0,
        }

    total = len(_FEEDBACK_STORE)
    avg_rating = sum(r.rating for r in _FEEDBACK_STORE) / total
    thumbs_up = sum(1 for r in _FEEDBACK_STORE if r.thumb == "up" or r.rating >= 4)
    thumbs_down = sum(1 for r in _FEEDBACK_STORE if r.thumb == "down" or r.rating <= 2)
    csat = (thumbs_up / total) * 100.0 if total > 0 else 0.0

    return {
        "total_submissions": total,
        "average_rating": round(avg_rating, 2),
        "thumbs_up_count": thumbs_up,
        "thumbs_down_count": thumbs_down,
        "csat_percentage": round(csat, 1),
    }


@feedback_router.post("/evals/test", response_model=ComprehensiveEvalReport)
async def evaluate_text(
    req: RunEvalRequest,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Runs automated heuristic evaluation on any input text or LLM response."""
    return HeuristicEvaluator.run_all(
        text=req.text,
        expect_json=req.expect_json,
        required_json_keys=req.required_json_keys,
        ground_truth_keywords=req.ground_truth_keywords,
        min_chars=req.min_chars,
        max_chars=req.max_chars,
    )
