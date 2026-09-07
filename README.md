# TruthGraph

**You bring the evidence. TruthGraph returns an inspectable verdict — supported, contradicted, or insufficient — you can put in a CI gate or an agent loop.**

[![CI](https://github.com/nishanttyagi28/truthgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/nishanttyagi28/truthgraph/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST_API-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/tests-34_passing-brightgreen)

Built by [Nishant Tyagi](https://github.com/nishanttyagi28) · follow the build on X [@tnishant838](https://x.com/tnishant838)

---

## The problem

LLMs and agents make claims constantly — captions, tool answers, RAG citations, “facts” in a reply.

Black-box judges don’t help much when you need to **debug**. A single score hides *why*. A paid LLM-as-judge adds cost, drift, and another model you can’t inspect. And if the evidence isn’t yours, you’re not evaluating your pipeline — you’re hoping the internet agrees.

You need something narrower and more honest: **given the evidence you already have**, does this claim look supported, contradicted, or under-specified — with reasons you can read.

---

## What TruthGraph is

TruthGraph is an **explainable claim-verification service**. You POST a claim and a list of evidence snippets. It does **not** browse the web or invent facts. It compares texts with a deterministic core (keywords, negation, numbers, source reliability), optionally splits compound claims into atomic pieces, and returns a structured dossier:

- `verdict`: `supported` | `contradicted` | `insufficient`
- `confidence` grounded in the submitted evidence (not a world-truth probability)
- matched keywords, reasons, and per-subclaim breakdowns when decomposition runs

**Evidence in → inspectable dossier out.** Same contract my [VisionEval](https://github.com/nishanttyagi28/VisionEval) consumer expects (`verdict` + `confidence` + `matched_keywords` + evidence lists), with richer v2 fields on top.

No paid API. No model download for the default path. FastAPI, CLI, optional Streamlit, Docker, CI.

---

## Who it’s for

- **Agent builders** who want a cheap, inspectable check before an agent trusts its own answer
- **RAG / eval engineers** gating “does this citation actually support the claim?”
- **VisionEval-style caption checks** — treat a model caption as a claim against ground-truth text
- **CI gates** — fail the build when a locked claim set flips from supported to contradicted

If you need a full fact-checker that crawls the web, this isn’t that product. If you need a **local, explainable support/contradict layer over your evidence**, it is.

---

## What I built

### Deterministic verification core

Keyword relevance, stop-word filtering, negation mismatch, numerical contradiction, reliability-weighted scoring — all inspectable.

```bash
python -m uvicorn app.api:app --reload
# POST /verify  →  supported | contradicted | insufficient
```

**Why it helps:** You can explain a fail in review without opening another LLM transcript.

### Claim decomposition → rolled-up verdict

Compound claims split into atomic sub-claims, verified one by one, then rolled into a parent verdict with reasons.

**Why it helps:** “Half right” stops looking like a clean pass. You see which piece broke.

### Hybrid scoring (optional)

Default path stays keyword/deterministic for CI. Flip a flag for offline TF-IDF cosine blended with keywords — no model download, no network.

**Why it helps:** Slightly better lexical overlap when wording drifts, without pulling torch or hitting an API.

### Source reputation registry

Built-in defaults (NASA, CDC, Wikipedia, anonymous blog, …) with caller override. `GET /sources` lists them.

**Why it helps:** Reliability isn’t a mystery constant — you can see and override it.

### Batch API, CLI, history, demo surface

- `POST /verify/batch`, `GET /health`, `GET /sources`
- CLI: JSON/YAML in, `--json` out
- Optional SQLite history behind `TRUTHGRAPH_HISTORY=1` (off by default)
- Streamlit demo (`streamlit_app.py`)
- Dockerfile + GitHub Actions pytest CI

**Why it helps:** Same engine from a curl, a pipeline job, or a quick UI — without rewriting the core.

---

## Quick demo

```bash
pip install -r requirements.txt
python -m uvicorn app.api:app --reload
```

```bash
curl -s http://127.0.0.1:8000/verify \
  -H 'Content-Type: application/json' \
  -d '{
    "claim": { "text": "Earth has one natural satellite." },
    "evidence": [
      {
        "text": "NASA confirms that Earth has one natural satellite called the Moon.",
        "source": "NASA",
        "reliability": 0.98
      }
    ]
  }'
```

Or skip the server:

```bash
python -m app.cli verify examples/sample_claim.json --json
```

You get a dossier — verdict, confidence, matched keywords, reasons — not a vibes score.

---

## Evidence-only metrics (honest)

TruthGraph scores **only the evidence you submit**. Confidence is strength of support/contradiction on that set after relevance and reliability weighting — not “probability the claim is true in the world.”

| Output | Meaning |
|--------|---------|
| `supported` | Relevant evidence leans support |
| `contradicted` | Relevant evidence leans contradiction (negation / number clash / opposing stance) |
| `insufficient` | No relevant evidence, or scores too close / sub-claims disagree |
| `confidence` | Strength of the decisive side on the submitted set (capped at 1.0) |
| Automated tests | **34** (deterministic path; CI on Python 3.11 / 3.12) |

No invented accuracy %, F1, or leaderboard numbers here.

---

## Install

```bash
git clone https://github.com/nishanttyagi28/truthgraph.git
cd truthgraph
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -v
```

### API

```bash
python -m uvicorn app.api:app --reload
```

Open `http://127.0.0.1:8000/docs`.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness + version / feature flags |
| `GET` | `/sources` | Source reputation registry |
| `POST` | `/verify` | Verify one claim (rich dossier) |
| `POST` | `/verify/batch` | Verify many claims |
| `GET` | `/history` | Recent rows when history is enabled |

`POST /verify` body:

```json
{
  "claim": { "text": "Earth has one natural satellite." },
  "evidence": [
    {
      "text": "Earth has one natural satellite called the Moon.",
      "source": "NASA",
      "reliability": 0.95
    }
  ],
  "decompose": false,
  "use_semantic": false,
  "use_registry": false
}
```

VisionEval-compatible core fields always present:

`claim`, `verdict`, `confidence`, `supporting_evidence`, `contradicting_evidence`, `matched_keywords`

Additive v2 fields: `reasons`, `subclaims`, `breakdown`, `meta`.

### CLI

```bash
python -m app.cli verify examples/sample_claim.json --json
python -m app.cli verify examples/sample_claim.yaml --json --semantic
python -m app.cli sources --json
```

### Sample script / Streamlit / Docker

```bash
python main.py                          # writes reports/verification_report.json
streamlit run streamlit_app.py          # optional demo UI
docker build -t truthgraph .
docker run --rm -p 8000:8000 truthgraph
```

### Environment flags

| Variable | Default | Effect |
|----------|---------|--------|
| `TRUTHGRAPH_SEMANTIC` | `0` | Enable hybrid TF-IDF cosine blend |
| `TRUTHGRAPH_KEYWORD_WEIGHT` | `0.7` | Keyword weight when semantic on |
| `TRUTHGRAPH_SEMANTIC_WEIGHT` | `0.3` | Semantic weight when semantic on |
| `TRUTHGRAPH_DECOMPOSE` | `1` | Decompose compound claims by default |
| `TRUTHGRAPH_HISTORY` | `0` | Persist dossiers to SQLite |
| `TRUTHGRAPH_HISTORY_DB` | `data/verification_history.sqlite3` | DB path |

---

## Architecture

```text
Client / CLI / Streamlit
        │
        ▼
   FastAPI (Pydantic)
        │
        ▼
 Claim decomposer (optional)
        │
        ▼
 Text analyzer  +  optional semantic (TF-IDF cosine)
        │
        ▼
 Evidence classifier (relevance / negation / numbers)
        │
        ▼
 Reliability weighting (± source registry)
        │
        ▼
 Verdict + confidence + reasons + subclaim rollup
        │
        ▼
 JSON dossier  (± SQLite history)
```

```text
truthgraph/
├── app/                 # api, cli, config, models, services
├── examples/
├── tests/               # 34 tests
├── streamlit_app.py
├── main.py
├── Dockerfile
├── .github/workflows/ci.yml
└── requirements.txt
```

---

## Limitations

- Does **not** fetch evidence from the internet.
- Does **not** guarantee submitted evidence is factually correct.
- Default path is lexical/deterministic; optional semantic is lightweight TF-IDF cosine, not a large embedding model.
- Source reputation defaults are heuristics; caller reliability wins unless `use_registry=true`.
- Confidence is evidence-relative, not a calibrated real-world probability.
- Claim decomposition is rule-based (sentences / light clause splits), not full linguistic parsing.

---

## Author

[Nishant Tyagi](https://github.com/nishanttyagi28) · [@tnishant838](https://x.com/tnishant838)
