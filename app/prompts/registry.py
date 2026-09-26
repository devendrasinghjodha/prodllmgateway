from typing import Dict, Any, List, Optional
import re
import datetime
from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    name: str
    version: int = 1
    template: str
    description: Optional[str] = None
    input_variables: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    model_override: Optional[str] = None
    temperature_override: Optional[float] = None


class PromptRegistry:
    """
    In-memory and persistent prompt registry with versioning, variable extraction,
    and runtime template rendering.
    """
    def __init__(self):
        # Key: name -> List of PromptTemplate sorted by version ascending
        self._prompts: Dict[str, List[PromptTemplate]] = {}
        self._seed_default_prompts()

    def _extract_variables(self, template: str) -> List[str]:
        """Extracts {variable_name} or {{variable_name}} tokens from template."""
        # Find single or double brace variables
        matches = re.findall(r"\{+([a-zA-Z_][a-zA-Z0-9_]*)\}+", template)
        return list(dict.fromkeys(matches))  # deduplicate preserving order

    def _seed_default_prompts(self):
        """Seeds standard built-in prompt templates."""
        self.register_prompt(
            name="summarize_text",
            template="You are an expert summarizer. Please summarize the following text concisely in {max_words} words:\n\n{text}",
            description="General purpose concise text summarization",
            tags=["summary", "nlp"],
        )
        self.register_prompt(
            name="customer_support_agent",
            template="You are a helpful customer support assistant for {company_name}. Always respond politely and professionally.\nCustomer query: {query}",
            description="Polite customer support persona",
            tags=["support", "persona"],
        )
        self.register_prompt(
            name="json_extractor",
            template="Extract the structured information from the text below according to schema: {schema}.\nInput text:\n{input_text}\n\nRespond ONLY with valid JSON.",
            description="Extracts strictly valid JSON from unstructured text",
            tags=["extraction", "json"],
        )

    def register_prompt(
        self,
        name: str,
        template: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        model_override: Optional[str] = None,
        temperature_override: Optional[float] = None,
    ) -> PromptTemplate:
        """
        Registers a new prompt or increments version if prompt with same name exists.
        """
        extracted_vars = self._extract_variables(template)
        if name not in self._prompts:
            self._prompts[name] = []
            version = 1
        else:
            version = len(self._prompts[name]) + 1

        prompt_obj = PromptTemplate(
            name=name,
            version=version,
            template=template,
            description=description,
            input_variables=extracted_vars,
            tags=tags or [],
            model_override=model_override,
            temperature_override=temperature_override,
        )
        self._prompts[name].append(prompt_obj)
        return prompt_obj

    def get_prompt(self, name: str, version: Optional[int] = None) -> Optional[PromptTemplate]:
        """
        Retrieves a prompt by name. If version is None, returns latest version.
        """
        versions = self._prompts.get(name)
        if not versions:
            return None
        if version is None:
            return versions[-1]
        for p in versions:
            if p.version == version:
                return p
        return None

    def list_prompts(self, tag: Optional[str] = None) -> List[PromptTemplate]:
        """
        Lists the latest versions of all registered prompts, optionally filtered by tag.
        """
        result = []
        for name, versions in self._prompts.items():
            latest = versions[-1]
            if tag is None or tag in latest.tags:
                result.append(latest)
        return result

    def get_prompt_history(self, name: str) -> List[PromptTemplate]:
        """Returns all versions for a prompt name."""
        return self._prompts.get(name, [])

    def render(self, name: str, variables: Dict[str, Any], version: Optional[int] = None) -> str:
        """
        Renders a prompt template with provided variables.
        """
        prompt = self.get_prompt(name, version=version)
        if not prompt:
            raise KeyError(f"Prompt '{name}' not found in registry")

        rendered = prompt.template
        for var_name in prompt.input_variables:
            val = variables.get(var_name, "")
            # Replace both {var} and {{var}}
            rendered = re.sub(r"\{+" + re.escape(var_name) + r"\}+", str(val), rendered)
        return rendered


# Global Singleton Registry
prompt_registry = PromptRegistry()
