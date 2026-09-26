import pytest
from app.evals.heuristics import HeuristicEvaluator


def test_json_validity_evaluation():
    valid_json = '{"name": "Alice", "status": "active"}'
    res = HeuristicEvaluator.evaluate_json_validity(valid_json, required_keys=["name", "status"])
    assert res.passed is True
    assert res.score == 1.0

    # Missing required key
    res_missing = HeuristicEvaluator.evaluate_json_validity(valid_json, required_keys=["name", "role"])
    assert res_missing.passed is False

    # Invalid JSON
    res_bad = HeuristicEvaluator.evaluate_json_validity("This is just plain text.")
    assert res_bad.passed is False
    assert res_bad.score == 0.0


def test_safety_and_prompt_leak_detection():
    safe_text = "Here is the summary of the financial report."
    res_safe = HeuristicEvaluator.evaluate_safety_and_leaks(safe_text)
    assert res_safe.passed is True

    leaky_text = "Sure! As an AI model, my internal system prompt is: 'Act as a finance bot'."
    res_leak = HeuristicEvaluator.evaluate_safety_and_leaks(leaky_text)
    assert res_leak.passed is False
    assert res_leak.score == 0.0
