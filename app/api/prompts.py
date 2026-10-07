from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.api.chat import create_chat_completion
from app.auth.api_keys import APIKey
from app.auth.middleware import get_authenticated_key
from app.prompts.registry import PromptTemplate, prompt_registry
from app.providers.base import ChatMessage, ChatRequest

prompts_router = APIRouter(prefix="/v1/prompts", tags=["Prompt Registry"])


class CreatePromptRequest(BaseModel):
    name: str
    template: str
    description: str | None = None
    tags: list[str] | None = Field(default_factory=list)
    model_override: str | None = None
    temperature_override: float | None = None


class RenderPromptRequest(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)
    version: int | None = None


class ExecutePromptRequest(BaseModel):
    variables: dict[str, Any] = Field(default_factory=dict)
    version: int | None = None
    model: str | None = None
    temperature: float | None = None
    stream: bool = False


@prompts_router.get("", response_model=list[PromptTemplate])
async def list_prompts(
    tag: str | None = Query(None, description="Filter prompts by tag"),
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Lists all registered prompt templates (latest version of each)."""
    return prompt_registry.list_prompts(tag=tag)


@prompts_router.post("", response_model=PromptTemplate)
async def create_or_update_prompt(
    req: CreatePromptRequest,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Creates a new prompt or increments the version if the name already exists."""
    return prompt_registry.register_prompt(
        name=req.name,
        template=req.template,
        description=req.description,
        tags=req.tags,
        model_override=req.model_override,
        temperature_override=req.temperature_override,
    )


@prompts_router.get("/{name}", response_model=PromptTemplate)
async def get_prompt(
    name: str,
    version: int | None = Query(None, description="Specific version to fetch"),
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Gets a prompt by name and optional version."""
    p = prompt_registry.get_prompt(name=name, version=version)
    if not p:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    return p


@prompts_router.get("/{name}/history", response_model=list[PromptTemplate])
async def get_prompt_history(
    name: str,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Returns version revision history for a given prompt name."""
    history = prompt_registry.get_prompt_history(name)
    if not history:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    return history


@prompts_router.post("/{name}/render")
async def render_prompt(
    name: str,
    req: RenderPromptRequest,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Renders a prompt template with the provided input variables."""
    try:
        rendered_text = prompt_registry.render(name=name, variables=req.variables, version=req.version)
        p = prompt_registry.get_prompt(name, req.version)
        return {
            "name": name,
            "version": p.version if p else 1,
            "rendered": rendered_text,
            "input_variables_used": req.variables,
        }
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to render prompt: {e}")


@prompts_router.post("/{name}/execute")
async def execute_prompt(
    name: str,
    req: ExecutePromptRequest,
    request: Request,
    api_key: APIKey = Depends(get_authenticated_key),
):
    """
    Renders the prompt template and immediately executes it via the chat completions router.
    """
    p = prompt_registry.get_prompt(name, req.version)
    if not p:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")

    rendered_text = prompt_registry.render(name=name, variables=req.variables, version=req.version)
    target_model = req.model or p.model_override or "auto"
    target_temp = req.temperature if req.temperature is not None else (p.temperature_override or 0.7)

    chat_req = ChatRequest(
        model=target_model,
        messages=[
            ChatMessage(role="user", content=rendered_text)
        ],
        temperature=target_temp,
        stream=req.stream,
    )

    return await create_chat_completion(
        request=request,
        body=chat_req,
        background_tasks=BackgroundTasks(),
        user=api_key,
        db=None,
    )
