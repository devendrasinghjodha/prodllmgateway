import pytest
from app.routing.router import router
from app.routing.policies import ABTestPolicy, LatencyBasedPolicy, CostOptimizedPolicy
from app.providers.base import ChatRequest, ChatMessage
from app.routing.scoring import scorer


def test_router_model_selection():
    req_gemini = ChatRequest(model="gemini", messages=[ChatMessage(role="user", content="hi")])
    providers = router.route(req_gemini)
    assert len(providers) > 0
    assert providers[0].name == "gemini"

    req_cheap = ChatRequest(model="cheap", messages=[ChatMessage(role="user", content="hi")])
    providers_cheap = router.route(req_cheap)
    assert providers_cheap[0].name == "openrouter"


def test_ab_testing_deterministic_partitioning():
    policy = ABTestPolicy()
    available = router.get_all_providers()
    req = ChatRequest(model="auto", messages=[ChatMessage(role="user", content="test")])

    # User 1 should always get the same primary
    result1_a = policy.select_providers(req, available, user_id="user_alice")
    result1_b = policy.select_providers(req, available, user_id="user_alice")
    assert result1_a[0].name == result1_b[0].name


def test_latency_based_routing():
    policy = LatencyBasedPolicy()
    scorer.record_latency("gemini", 800.0)
    scorer.record_latency("openrouter", 1200.0)
    scorer.record_latency("agnes", 300.0)

    available = router.get_all_providers()
    req = ChatRequest(model="auto", messages=[ChatMessage(role="user", content="test")])
    ordered = policy.select_providers(req, available)

    assert ordered[0].name == "agnes"
