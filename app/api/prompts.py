from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, Field

from app.prompts.registry import prompt_registry, PromptTemplate
from app.auth.middleware import get_authenticated_key
from app.auth.api_keys import APIKey
from app.api.chat import chat_completions, ChatCompletionRequest, ChatMessage

prompts_router = APIRouter(prefix="/v1/prompts", tags=["Prompt Registry"])


class CreatePromptRequest(BaseModel):
    name: str
    template: str
    description: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    model_override: Optional[str] = None
    temperature_override: Optional[float] = None


class RenderPromptRequest(BaseModel):
    variables: Dict[str, Any] = Field(default_factory=dict)
    version: Optional[int] = None


class ExecutePromptRequest(BaseModel):
    variables: Dict[str, Any] = Field(default_factory=dict)
    version: Optional[int] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    stream: bool = False


@prompts_router.get("", response_model=List[PromptTemplate])
async def list_prompts(
    tag: Optional[str] = Query(None, description="Filter prompts by tag"),
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
    version: Optional[int] = Query(None, description="Specific version to fetch"),
    api_key: APIKey = Depends(get_authenticated_key),
):
    """Gets a prompt by name and optional version."""
    p = prompt_registry.get_prompt(name=name, version=version)
    if not p:
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    return p


@prompts_router.get("/{name}/history", response_model=List[PromptTemplate])
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

    chat_req = ChatCompletionRequest(
        model=target_model,
        messages=[
            ChatMessage(role="user", content=rendered_text)
        ],
        temperature=target_temp,
        stream=req.stream,
    )

    return await chat_completions(chat_req, request, api_key)
