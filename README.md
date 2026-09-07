# TruthGraph

**Deterministic evidence gate for AI agents & RAG — `ALLOW` / `REVIEW` / `BLOCK` with an inspectable dossier.**

You bring the evidence (or RAG citations). TruthGraph returns a verdict *and* an action decision you can put in front of a tool call, a citation, or a CI job — without a paid LLM judge.

[![CI](https://github.com/nishanttyagi28/truthgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/nishanttyagi28/truthgraph/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST_API-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/tests-71_passing-brightgreen)

Built by [Nishant Tyagi](https://github.com/nishanttyagi28) · follow the build on X [@tnishant838](https://x.com/tnishant838)

---

## Why this sells

| Business outcome | How TruthGraph helps |
|------------------|----------------------|
| **Reduce hallucination-driven actions** | Gate tool calls: only `ALLOW` when evidence supports the claim above a threshold |
| **CI-gate agent claims** | Golden suite + lockfile fails the build when expected verdicts flip |
| **Audit trail for stakeholders** | Markdown/JSON dossier: claim, evidence, scores, decision, policy, timestamp |
| **RAG citation honesty** | Treat `answer` + `citations[]` as claim/evidence with citation-aware reasons |

**Not** “another fact checker that browses the web.” **Not** “LLM-as-judge.” Evidence in → inspectable dossier + decision out.

---

## 60-second sell demo

```bash
pip install -r requirements.txt

# 1) Agent tool gate — ALLOW / REVIEW / BLOCK
python -m app.cli gate examples/sample_claim.json --json --no-decompose

# 2) RAG citation gate
python -m app.cli gate examples/sample_rag.json --policy rag_citation_gate --json --no-decompose

# 3) Compliance audit for stakeholders
python -m app.cli audit examples/sample_claim.json --out reports/demo --no-decompose

# 4) CI golden suite (fails if verdicts drift)
python -m app.cli suite run examples/golden/suite.yaml
python -m app.cli suite gate examples/golden/suite.yaml --lockfile examples/golden/suite.lock.json
```

Or hit the API:

```bash
python -m uvicorn app.api:app --reload
curl -s http://127.0.0.1:8000/gate -H 'Content-Type: application/json' -d '{
  "claim": {"text": "Earth has one natural satellite."},
  "evidence": [{"text": "NASA confirms that Earth has one natural satellite called the Moon.",
                "source": "NASA", "reliability": 0.98}],
  "policy_id": "agent_tool_gate",
  "decompose": false
}'
```

You get: `decision`, `verdict`, `confidence`, `reasons`, `policy_id` — plus the VisionEval-compatible verification dossier.

---

## Product surfaces

### 1. Decision policy engine

Maps `verdict` + `confidence` (+ optional risk tags) → **`ALLOW` | `REVIEW` | `BLOCK`**.

Documented presets (also under `app/policies/*.yaml`):

| Preset | Floor | Intent |
|--------|-------|--------|
| `agent_tool_gate` | 0.55 | Before a side-effecting agent tool |
| `rag_citation_gate` | 0.65 | Does this citation support the answer? |
| `caption_gate` | 0.45 | VisionEval-style caption checks |

Configure via env (`TRUTHGRAPH_POLICY_*`), YAML, or request body. Risk tags like `payment` / `delete` can force `BLOCK`; `pii` can escalate `ALLOW` → `REVIEW`.

### 2. Agent gate

- FastAPI `POST /gate` — verify + policy in one call
- Python helper: `from app.services.gate import gate, gate_context, gated`
- Clear JSON: `decision`, `verdict`, `confidence`, `reasons`, `policy_id`

```python
from app.services.gate import gate, gate_context
from app.models.claim import Claim
from app.models.evidence import Evidence

claim = Claim(text="Earth has one natural satellite.")
evidence = [Evidence(text="NASA confirms Earth has one natural satellite called the Moon.",
                     source="NASA", reliability=0.98)]

gr = gate(claim, evidence, policy_id="agent_tool_gate", decompose=False)
if gr.allowed():
    call_tool()

# Or block by default unless ALLOW:
with gate_context(claim, evidence, decompose=False):
    call_tool()
```

### 3. Audit / compliance dossier

```bash
python -m app.cli audit examples/sample_claim.json --out reports/audit
# → reports/audit/audit.json + audit.md
```

Streamlit demo includes **Export audit** download buttons.

### 4. Golden claim suite + CI gate

```text
examples/golden/suite.yaml      # locked scenarios
examples/golden/suite.lock.json # expected verdicts/decisions
```

```bash
python -m app.cli suite run examples/golden/suite.yaml
python -m app.cli suite gate examples/golden/suite.yaml --lockfile examples/golden/suite.lock.json
```

Wired in GitHub Actions alongside pytest (VisionEval traps-gate energy: fail when expectations flip).

### 5. RAG citation verify mode

Primary business use case — ground an answer on its citations:

```bash
python -m app.cli gate examples/sample_rag.json --policy rag_citation_gate --json
```

API: send `answer` + `citations[]` to `/verify` or `/gate` (or set `"mode": "rag"` with claim/evidence). Reasons include which citations supported vs contradicted.

### 6. Deterministic verification core (unchanged contract)

`POST /verify` still returns VisionEval-compatible fields:

`claim`, `verdict`, `confidence`, `supporting_evidence`, `contradicting_evidence`, `matched_keywords`

Additive: `reasons`, `subclaims`, `breakdown`, `meta`.

---

## The problem (honest)

LLMs and agents make claims constantly — tool arguments, RAG answers, captions.

Black-box judges don’t help when you need to **debug**. A paid LLM-as-judge adds cost, drift, and another model you can’t inspect. If the evidence isn’t yours, you’re not evaluating your pipeline — you’re hoping the internet agrees.

TruthGraph is narrower: **given the evidence you already have**, does this claim look supported, contradicted, or under-specified — and should the agent **ALLOW**, **REVIEW**, or **BLOCK**.

---

## Evidence-only metrics (honest)

TruthGraph scores **only the evidence you submit**. Confidence is strength of support/contradiction on that set — not “probability the claim is true in the world.”

| Output | Meaning |
|--------|---------|
| `supported` / `contradicted` / `insufficient` | Evidence stance after relevance + reliability |
| `ALLOW` / `REVIEW` / `BLOCK` | Policy decision over verdict + confidence (+ risk tags) |
| Automated tests | **71** offline, deterministic (CI on Python 3.11 / 3.12) |
| Golden suite | **7** locked cases gated in CI |

No invented accuracy %, F1, or “used by Fortune 500.”

---

## Install

```bash
git clone https://github.com/nishanttyagi28/truthgraph.git
cd truthgraph
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -v
```

### API

```bash
python -m uvicorn app.api:app --reload
```

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness + version / flags |
| `GET` | `/sources` | Source reputation registry |
| `GET` | `/policies` | Decision-policy presets |
| `POST` | `/verify` | Verify one claim (VisionEval-compatible) |
| `POST` | `/verify/batch` | Verify many claims |
| `POST` | `/gate` | Verify + ALLOW/REVIEW/BLOCK |
| `GET` | `/history` | Recent rows when history enabled |

### CLI

```bash
python -m app.cli verify examples/sample_claim.json --json
python -m app.cli gate examples/sample_claim.json --policy agent_tool_gate --json
python -m app.cli audit examples/sample_claim.json --out reports/audit
python -m app.cli suite run examples/golden/suite.yaml
python -m app.cli suite gate examples/golden/suite.yaml --lockfile examples/golden/suite.lock.json
python -m app.cli policies --json
```

### Environment flags

| Variable | Default | Effect |
|----------|---------|--------|
| `TRUTHGRAPH_SEMANTIC` | `0` | Hybrid TF-IDF cosine blend |
| `TRUTHGRAPH_DECOMPOSE` | `1` | Decompose compound claims |
| `TRUTHGRAPH_HISTORY` | `0` | Persist dossiers to SQLite |
| `TRUTHGRAPH_POLICY` | `agent_tool_gate` | Default gate preset |
| `TRUTHGRAPH_POLICY_MIN_CONFIDENCE_ALLOW` | (preset) | Override allow floor |
| `TRUTHGRAPH_POLICY_BLOCK_ON_CONTRADICTED` | (preset) | Block contradicted |
| `TRUTHGRAPH_POLICY_BLOCK_RISK_TAGS` | (preset) | Comma-separated force-BLOCK tags |

---

## Architecture

```text
Claim / answer + evidence / citations
        │
        ▼
 Claim decomposer (optional)
        │
        ▼
 Text analyzer + optional semantic (TF-IDF)
        │
        ▼
 Verdict + confidence + reasons   ←── /verify (stable)
        │
        ▼
 Policy engine (thresholds + risk tags)
        │
        ▼
 ALLOW | REVIEW | BLOCK + audit dossier  ←── /gate
        │
        ▼
 Golden suite lockfile (CI)
```

```text
truthgraph/
├── app/
│   ├── api.py              # /verify, /gate, /policies
│   ├── cli.py              # verify, gate, audit, suite
│   ├── policies/           # YAML presets
│   └── services/
│       ├── policy.py       # decision engine
│       ├── gate.py         # agent helper / decorator
│       ├── audit.py        # Markdown + JSON export
│       ├── rag.py          # citation verify mode
│       ├── suite.py        # golden suite + lockfile gate
│       └── verifier*.py    # deterministic core
├── examples/golden/        # suite + lockfile
├── tests/
└── .github/workflows/ci.yml
```

---

## Limitations

- Does **not** fetch evidence from the internet.
- Does **not** guarantee submitted evidence is factually correct.
- Default path is lexical/deterministic; optional semantic is lightweight TF-IDF cosine.
- Policy thresholds are heuristics you own — tune per product surface.
- Confidence is evidence-relative, not a calibrated world probability.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for v2.1.0 (evidence gate / business packaging).

---

## Author

[Nishant Tyagi](https://github.com/nishanttyagi28) · [@tnishant838](https://x.com/tnishant838)
