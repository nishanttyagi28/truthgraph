# Changelog

## 2.1.0 — Evidence gate (business packaging)

Positioning: **Deterministic evidence gate for AI agents & RAG — ALLOW / REVIEW / BLOCK with an inspectable dossier.**

### Added
- **Decision policy engine** (`app/services/policy.py`) with presets `agent_tool_gate`, `rag_citation_gate`, `caption_gate`; env / YAML / request overrides; risk tags.
- **`POST /gate`** and Python helpers (`gate`, `gate_context`, `gated`, `require_allow`).
- **Audit export** — Markdown + JSON dossiers; CLI `truthgraph audit`; Streamlit export buttons.
- **Golden claim suite** — `examples/golden/suite.yaml` + lockfile; CLI `suite run` / `suite gate`; CI job.
- **RAG citation verify mode** — `answer` + `citations[]` on `/verify` and `/gate`; citation-aware reasons.
- **`GET /policies`** — documented presets.
- Substantial offline tests for policy / gate / suite / audit / RAG.

### Changed
- Version bump to **2.1.0**.
- README leads with business outcomes (agent gate, RAG citations, audit trail, CI lockfile).
- CI runs golden suite gate alongside pytest.

### Compatibility
- **`POST /verify` contract unchanged** (VisionEval core fields preserved).
- No paid APIs; default path remains offline / deterministic.
