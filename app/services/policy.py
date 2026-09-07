"""Decision policy engine: map verification → ALLOW | REVIEW | BLOCK.

Deterministic thresholds over verdict + confidence (+ optional risk tags).
Configurable via env, YAML, or request body. No LLM judge.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.results import VerificationResult, Verdict

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

Decision = Literal["ALLOW", "REVIEW", "BLOCK"]

PolicyId = Literal["agent_tool_gate", "rag_citation_gate", "caption_gate", "custom"]

_POLICIES_DIR = Path(__file__).resolve().parent.parent / "policies"


class PolicyConfig(BaseModel):
    """Thresholds that turn a verification dossier into an action decision."""

    policy_id: str = "agent_tool_gate"
    description: str = ""
    block_on_contradicted: bool = True
    min_confidence_allow: float = Field(default=0.55, ge=0.0, le=1.0)
    block_low_confidence: bool = False
    block_on_insufficient: bool = False
    review_on_insufficient: bool = True
    block_risk_tags: list[str] = Field(default_factory=list)
    review_risk_tags: list[str] = Field(default_factory=list)


class PolicyDecision(BaseModel):
    """Inspectable policy outcome attached to a gate response."""

    decision: Decision
    policy_id: str
    reasons: list[str] = Field(default_factory=list)
    thresholds: dict[str, Any] = Field(default_factory=dict)


def _builtin_presets() -> dict[str, PolicyConfig]:
    """Fallback presets if YAML files are unavailable."""
    return {
        "agent_tool_gate": PolicyConfig(
            policy_id="agent_tool_gate",
            description="Agent tool gate: BLOCK contradicted; ALLOW supported≥0.55; else REVIEW.",
            min_confidence_allow=0.55,
            block_risk_tags=["irreversible", "payment", "delete"],
            review_risk_tags=["pii", "external_write"],
        ),
        "rag_citation_gate": PolicyConfig(
            policy_id="rag_citation_gate",
            description="RAG citation gate: ALLOW supported≥0.65; BLOCK contradicted; else REVIEW.",
            min_confidence_allow=0.65,
            block_risk_tags=["medical", "legal"],
            review_risk_tags=["ungrounded"],
        ),
        "caption_gate": PolicyConfig(
            policy_id="caption_gate",
            description="Caption gate: ALLOW supported≥0.45; BLOCK contradicted; else REVIEW.",
            min_confidence_allow=0.45,
        ),
    }


def _load_presets() -> dict[str, PolicyConfig]:
    presets = _builtin_presets()
    if yaml is None or not _POLICIES_DIR.is_dir():
        return presets
    for path in sorted(_POLICIES_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg = PolicyConfig(**data)
                presets[cfg.policy_id] = cfg
        except Exception:  # pragma: no cover — keep builtins on bad YAML
            continue
    return presets


PRESETS: dict[str, PolicyConfig] = _load_presets()


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def default_policy_id() -> str:
    return os.getenv("TRUTHGRAPH_POLICY", "agent_tool_gate").strip() or "agent_tool_gate"


def get_preset(policy_id: str | None = None) -> PolicyConfig:
    """Return a documented preset, falling back to agent_tool_gate."""
    pid = (policy_id or default_policy_id()).strip()
    if pid in PRESETS:
        return PRESETS[pid].model_copy(deep=True)
    cfg = PRESETS["agent_tool_gate"].model_copy(deep=True)
    cfg.policy_id = pid
    cfg.description = cfg.description + f" (custom id={pid!r})"
    return cfg


def policy_from_env(base: PolicyConfig | None = None) -> PolicyConfig:
    """Overlay TRUTHGRAPH_POLICY_* environment variables on a preset."""
    cfg = (base or get_preset()).model_copy(deep=True)
    cfg.min_confidence_allow = _env_float(
        "TRUTHGRAPH_POLICY_MIN_CONFIDENCE_ALLOW", cfg.min_confidence_allow
    )
    cfg.block_on_contradicted = _env_bool(
        "TRUTHGRAPH_POLICY_BLOCK_ON_CONTRADICTED", cfg.block_on_contradicted
    )
    cfg.block_low_confidence = _env_bool(
        "TRUTHGRAPH_POLICY_BLOCK_LOW_CONFIDENCE", cfg.block_low_confidence
    )
    cfg.block_on_insufficient = _env_bool(
        "TRUTHGRAPH_POLICY_BLOCK_ON_INSUFFICIENT", cfg.block_on_insufficient
    )
    cfg.review_on_insufficient = _env_bool(
        "TRUTHGRAPH_POLICY_REVIEW_ON_INSUFFICIENT", cfg.review_on_insufficient
    )
    tags = os.getenv("TRUTHGRAPH_POLICY_BLOCK_RISK_TAGS")
    if tags is not None:
        cfg.block_risk_tags = [t.strip() for t in tags.split(",") if t.strip()]
    review_tags = os.getenv("TRUTHGRAPH_POLICY_REVIEW_RISK_TAGS")
    if review_tags is not None:
        cfg.review_risk_tags = [t.strip() for t in review_tags.split(",") if t.strip()]
    return cfg


def load_policy_yaml(path: str | Path) -> PolicyConfig:
    """Load a PolicyConfig from a YAML (or JSON) file."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is required to load policy YAML")
        data = yaml.safe_load(text)
    else:
        import json

        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("Policy file must contain a mapping/object")
    return PolicyConfig(**data)


def merge_policy(
    *,
    policy_id: str | None = None,
    overrides: dict[str, Any] | PolicyConfig | None = None,
    yaml_path: str | Path | None = None,
    apply_env: bool = True,
) -> PolicyConfig:
    """Resolve effective policy: preset → YAML → env → request overrides."""
    if yaml_path is not None:
        cfg = load_policy_yaml(yaml_path)
        if policy_id:
            cfg.policy_id = policy_id
    else:
        cfg = get_preset(policy_id)
    if apply_env:
        cfg = policy_from_env(cfg)
    if overrides is not None:
        if isinstance(overrides, PolicyConfig):
            data = cfg.model_dump()
            data.update(overrides.model_dump(exclude_unset=False))
            if not data.get("description"):
                data["description"] = cfg.description
            cfg = PolicyConfig(**data)
        elif isinstance(overrides, dict) and overrides:
            data = cfg.model_dump()
            data.update({k: v for k, v in overrides.items() if v is not None})
            cfg = PolicyConfig(**data)
    return cfg


def decide(
    verdict: Verdict,
    confidence: float,
    *,
    policy: PolicyConfig | None = None,
    risk_tags: list[str] | None = None,
) -> PolicyDecision:
    """Map verdict + confidence (+ risk tags) → ALLOW | REVIEW | BLOCK."""
    cfg = policy or policy_from_env(get_preset())
    tags = [t.strip().lower() for t in (risk_tags or []) if t and t.strip()]
    reasons: list[str] = []
    decision: Decision = "REVIEW"

    block_hits = [t for t in tags if t in {x.lower() for x in cfg.block_risk_tags}]
    review_hits = [t for t in tags if t in {x.lower() for x in cfg.review_risk_tags}]
    if block_hits:
        decision = "BLOCK"
        reasons.append(f"Risk tag(s) require BLOCK: {', '.join(block_hits)}.")
    elif verdict == "contradicted" and cfg.block_on_contradicted:
        decision = "BLOCK"
        reasons.append(
            f"Verdict is contradicted (confidence={confidence:.3f}); "
            "policy block_on_contradicted=true."
        )
    elif verdict == "supported":
        if confidence >= cfg.min_confidence_allow:
            decision = "ALLOW"
            reasons.append(
                f"Verdict supported with confidence {confidence:.3f} "
                f">= min_confidence_allow {cfg.min_confidence_allow:.3f}."
            )
        elif cfg.block_low_confidence:
            decision = "BLOCK"
            reasons.append(
                f"Supported but confidence {confidence:.3f} "
                f"< min_confidence_allow {cfg.min_confidence_allow:.3f}; "
                "block_low_confidence=true."
            )
        else:
            decision = "REVIEW"
            reasons.append(
                f"Supported but confidence {confidence:.3f} "
                f"< min_confidence_allow {cfg.min_confidence_allow:.3f}; needs review."
            )
    elif verdict == "insufficient":
        if cfg.block_on_insufficient:
            decision = "BLOCK"
            reasons.append("Verdict insufficient; policy block_on_insufficient=true.")
        elif cfg.review_on_insufficient:
            decision = "REVIEW"
            reasons.append("Verdict insufficient; policy routes to REVIEW.")
        else:
            decision = "ALLOW"
            reasons.append("Verdict insufficient; policy allows through.")
    else:  # pragma: no cover
        decision = "REVIEW"
        reasons.append(f"Unhandled verdict {verdict!r}; defaulting to REVIEW.")

    if review_hits and decision == "ALLOW":
        decision = "REVIEW"
        reasons.append(f"Risk tag(s) escalate ALLOW→REVIEW: {', '.join(review_hits)}.")

    return PolicyDecision(
        decision=decision,
        policy_id=cfg.policy_id,
        reasons=reasons,
        thresholds={
            "min_confidence_allow": cfg.min_confidence_allow,
            "block_on_contradicted": cfg.block_on_contradicted,
            "block_low_confidence": cfg.block_low_confidence,
            "block_on_insufficient": cfg.block_on_insufficient,
            "review_on_insufficient": cfg.review_on_insufficient,
            "block_risk_tags": list(cfg.block_risk_tags),
            "review_risk_tags": list(cfg.review_risk_tags),
        },
    )


def decide_from_result(
    result: VerificationResult,
    *,
    policy: PolicyConfig | None = None,
    risk_tags: list[str] | None = None,
) -> PolicyDecision:
    return decide(
        result.verdict,
        result.confidence,
        policy=policy,
        risk_tags=risk_tags,
    )


def list_presets() -> dict[str, dict[str, Any]]:
    """Public documentation payload for presets."""
    return {
        pid: {
            "policy_id": cfg.policy_id,
            "description": cfg.description,
            "min_confidence_allow": cfg.min_confidence_allow,
            "block_on_contradicted": cfg.block_on_contradicted,
            "block_low_confidence": cfg.block_low_confidence,
            "block_on_insufficient": cfg.block_on_insufficient,
            "review_on_insufficient": cfg.review_on_insufficient,
            "block_risk_tags": list(cfg.block_risk_tags),
            "review_risk_tags": list(cfg.review_risk_tags),
        }
        for pid, cfg in PRESETS.items()
    }
