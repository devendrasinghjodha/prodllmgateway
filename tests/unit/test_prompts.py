import pytest
from app.prompts.registry import PromptRegistry


def test_prompt_registration_and_versioning():
    reg = PromptRegistry()
    p1 = reg.register_prompt(
        name="test_prompt",
        template="Hello {name}, welcome to {place}!",
        description="Greeting template",
    )
    assert p1.version == 1
    assert "name" in p1.input_variables
    assert "place" in p1.input_variables

    # Registering same name increments version
    p2 = reg.register_prompt(
        name="test_prompt",
        template="Hi {name}, how are things at {place} in {year}?",
    )
    assert p2.version == 2
    assert "year" in p2.input_variables

    # Get latest
    latest = reg.get_prompt("test_prompt")
    assert latest.version == 2

    # Get specific version
    v1 = reg.get_prompt("test_prompt", version=1)
    assert v1.version == 1


def test_prompt_rendering():
    reg = PromptRegistry()
    reg.register_prompt(
        name="translate",
        template="Translate the following text to {target_lang}: {text}",
    )

    rendered = reg.render("translate", {"target_lang": "French", "text": "Good morning"})
    assert rendered == "Translate the following text to French: Good morning"
