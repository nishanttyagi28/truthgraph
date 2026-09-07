# TruthGraph

Explainable claim verification: you bring the evidence, TruthGraph returns a structured verdict you can inspect.

[![CI](https://github.com/nishanttyagi28/truthgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/nishanttyagi28/truthgraph/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-REST_API-009688?logo=fastapi&logoColor=white)
![Tests](https://img.shields.io/badge/tests-34_passing-brightgreen)

Follow the build on X [@tnishant838](https://x.com/tnishant838).

---

## In simple terms

If a recruiter asks “so what does this project actually do?”, here’s how I’d answer.

You give TruthGraph a **claim** and the **evidence** you already have. It does **not** browse the web or invent facts. It compares the texts with deterministic rules (keywords, negation, numbers, source reliability), optionally splits a compound claim into smaller pieces, and returns:

- a verdict: `supported` | `contradicted` | `insufficient`
- a confidence score grounded in the submitted evidence
- matched keywords, reasons, and (when useful) per-subclaim breakdowns

That’s the whole idea: **evidence in → inspectable dossier out.**

**Consumer:** [VisionEval](https://github.com/nishanttyagi28/VisionEval) vendors a compatible copy of this core to check vision-model captions against ground-truth text. The shared contract is `verdict` + `confidence` + `matched_keywords` (plus evidence lists). TruthGraph v2 keeps those fields stable and adds richer dossier fields on top.

---

## What I built

### Deterministic verification core

Keyword relevance, stop-word filtering, negation mismatch, numerical contradiction, and reliability-weighted scoring — all inspectable, no paid API.

```bash
python -m uvicorn app.api:app --reload
# POST /verify  →  supported | contradicted | insufficient
```

### Claim decomposition → rolled-up verdict

Compound claims can be split into atomic sub-claims, verified one by one, then rolled into a parent verdict with reasons.

### Hybrid scoring (optional)

Keep the keyword path for CI and default runs. Flip a flag for lightweight offline TF-IDF cosine similarity blended with keywords. No model download, no network.

### Source reputation registry

Built-in defaults (e.g. NASA, CDC, Wikipedia, anonymous blog) with caller override. `GET /sources` lists them.

### Batch API, CLI, optional history & demo

- `POST /verify/batch`, `GET /health`, `GET /sources`
- CLI: JSON/YAML in, `--json` out
- Optional SQLite history behind `TRUTHGRAPH_HISTORY=1` (default off)
- Optional Streamlit demo (`streamlit_app.py`)
- Dockerfile + GitHub Actions pytest CI

---

## Evidence-only metrics (honest)

TruthGraph scores **only the evidence you submit**. Confidence is not “probability the claim is true in the world.” It reflects internal support/contradiction strength after relevance and reliability weighting.

| Output | Meaning |
|--------|---------|
| `supported` | Relevant evidence leans support |
| `contradicted` | Relevant evidence leans contradiction (negation / number clash / opposing stance) |
| `insufficient` | No relevant evidence, or scores too close / sub-claims disagree |
| `confidence` | Strength of the decisive side on the submitted set (capped at 1.0) |

No invented accuracy %, F1, or benchmark leaderboard numbers in this README.

---

## Quick start

```bash
git clone https://github.com/nishanttyagi28/truthgraph.git
cd truthgraph
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Tests

```bash
python -m pytest -v
```

Default tests use the deterministic keyword path only (no network).

### API

```bash
python -m uvicorn app.api:app --reload
```

Open `http://127.0.0.1:8000/docs`.

### CLI

```bash
python -m app.cli verify examples/sample_claim.json --json
python -m app.cli verify examples/sample_claim.yaml --json --semantic
python -m app.cli sources --json
```

### Sample script

```bash
python main.py
# writes reports/verification_report.json
```

### Streamlit demo (optional)

```bash
streamlit run streamlit_app.py
```

### Docker

```bash
docker build -t truthgraph .
docker run --rm -p 8000:8000 truthgraph
```

---

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness + version / feature flags |
| `GET` | `/sources` | Source reputation registry |
| `POST` | `/verify` | Verify one claim (rich dossier) |
| `POST` | `/verify/batch` | Verify many claims |
| `GET` | `/history` | Recent rows when history is enabled |

### `POST /verify` example

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

Response always includes VisionEval-compatible core fields:

`claim`, `verdict`, `confidence`, `supporting_evidence`, `contradicting_evidence`, `matched_keywords`

Additive v2 fields: `reasons`, `subclaims`, `breakdown`, `meta`.

---

## Environment flags

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

---

## Project structure

```text
truthgraph/
├── app/
│   ├── api.py
│   ├── cli.py
│   ├── config.py
│   ├── models/
│   └── services/          # analyzer, verifier*, decomposer, semantic, reputation, history
│                          # *verifier.py re-exports verifier_impl (atomic + rollup)
├── examples/
├── tests/
├── streamlit_app.py
├── main.py
├── Dockerfile
├── .github/workflows/ci.yml
└── requirements.txt
```

---

## Build note

As noted on my X account [@tnishant838](https://x.com/tnishant838), TruthGraph is hands-on practice. I own the product direction, architecture, and acceptance of changes. AI assistance was used for parts of implementation and debugging; everything is reviewed and tested against the intended design.

---

## Limitations

- Does **not** fetch evidence from the internet.
- Does **not** guarantee that submitted evidence is factually correct.
- Default path is lexical/deterministic; optional semantic similarity is lightweight TF-IDF cosine, not a large embedding model.
- Source reputation defaults are heuristics; caller reliability overrides unless `use_registry=true`.
- Confidence is evidence-relative, not a calibrated probability of real-world truth.
- Claim decomposition is rule-based (sentences / light clause splits), not full linguistic parsing.

---

## Author

Built by [Nishant Tyagi](https://github.com/nishanttyagi28) · [@tnishant838](https://x.com/tnishant838)
