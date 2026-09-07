"""Tests for the decision policy engine."""

from app.services.policy import (
    PolicyConfig,
    decide,
    get_preset,
    list_presets,
    load_policy_yaml,
    merge_policy,
    policy_from_env,
)


def test_presets_documented():
    presets = list_presets()
    assert "agent_tool_gate" in presets
    assert "rag_citation_gate" in presets
    assert "caption_gate" in presets
    assert presets["rag_citation_gate"]["min_confidence_allow"] > presets["agent_tool_gate"][
        "min_confidence_allow"
    ]


def test_allow_supported_high_confidence():
    d = decide("supported", 0.9, policy=get_preset("agent_tool_gate"))
    assert d.decision == "ALLOW"
    assert d.policy_id == "agent_tool_gate"


def test_block_contradicted():
    d = decide("contradicted", 0.8, policy=get_preset("agent_tool_gate"))
    assert d.decision == "BLOCK"


def test_review_insufficient():
    d = decide("insufficient", 0.0, policy=get_preset("agent_tool_gate"))
    assert d.decision == "REVIEW"


def test_review_low_confidence_supported():
    d = decide("supported", 0.4, policy=get_preset("agent_tool_gate"))
    assert d.decision == "REVIEW"


def test_block_low_confidence_when_configured():
    cfg = PolicyConfig(
        policy_id="custom",
        min_confidence_allow=0.7,
        block_low_confidence=True,
    )
    d = decide("supported", 0.5, policy=cfg)
    assert d.decision == "BLOCK"


def test_risk_tag_forces_block():
    d = decide(
        "supported",
        0.99,
        policy=get_preset("agent_tool_gate"),
        risk_tags=["payment"],
    )
    assert d.decision == "BLOCK"


def test_risk_tag_escalates_allow_to_review():
    d = decide(
        "supported",
        0.99,
        policy=get_preset("agent_tool_gate"),
        risk_tags=["pii"],
    )
    assert d.decision == "REVIEW"


def test_load_policy_yaml():
    cfg = load_policy_yaml("app/policies/rag_citation_gate.yaml")
    assert cfg.policy_id == "rag_citation_gate"
    assert cfg.min_confidence_allow == 0.65


def test_merge_policy_overrides(monkeypatch):
    monkeypatch.delenv("TRUTHGRAPH_POLICY_MIN_CONFIDENCE_ALLOW", raising=False)
    cfg = merge_policy(
        policy_id="agent_tool_gate",
        overrides={"min_confidence_allow": 0.8},
        apply_env=False,
    )
    assert cfg.min_confidence_allow == 0.8


def test_policy_from_env(monkeypatch):
    monkeypatch.setenv("TRUTHGRAPH_POLICY_MIN_CONFIDENCE_ALLOW", "0.77")
    monkeypatch.setenv("TRUTHGRAPH_POLICY_BLOCK_ON_INSUFFICIENT", "1")
    cfg = policy_from_env(get_preset("agent_tool_gate"))
    assert cfg.min_confidence_allow == 0.77
    assert cfg.block_on_insufficient is True


def test_block_on_insufficient():
    cfg = PolicyConfig(policy_id="strict", block_on_insufficient=True)
    d = decide("insufficient", 0.0, policy=cfg)
    assert d.decision == "BLOCK"
