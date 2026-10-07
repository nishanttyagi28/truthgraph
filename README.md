# TruthGraph

Checks a claim against evidence you supply and returns a verdict plus an `ALLOW` / `REVIEW` / `BLOCK` decision. It runs offline and is deterministic, with no LLM judge.

[![CI](https://github.com/nishanttyagi28/truthgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/nishanttyagi28/truthgraph/actions/workflows/ci.yml)

Agents and RAG pipelines constantly make claims: a tool argument, an answer with citations, an image caption. TruthGraph answers a narrow question about each one: given the evidence you already have, is this claim supported, contradicted, or not covered? It then applies a policy that turns the result into a decision you can put in front of a tool call, a citation, or a CI job. Every decision comes with plain-text reasons, so you can see why it was made.

It doesn't search the web, and it doesn't judge whether your evidence is true.

## Install

Python 3.11 or newer.

```bash
git clone https://github.com/nishanttyagi28/truthgraph.git
cd truthgraph
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

There is no PyPI package. Run it from the repository root.

## Quick start

`examples/sample_claim.json` has one claim and two pieces of evidence:

```json
{
  "claim": {"text": "Earth has one natural satellite."},
  "evidence": [
    {"text": "NASA confirms that Earth has one natural satellite called the Moon.", "source": "NASA", "reliability": 0.98},
    {"text": "Mars has two moons named Phobos and Deimos.", "source": "Space Magazine", "reliability": 0.75}
  ]
}
```

```bash
python -m app.cli gate examples/sample_claim.json --json --no-decompose
```

This returns `"decision": "ALLOW"`, `"verdict": "supported"`, `"confidence": 0.98`, along with the reasons: the NASA line supports the claim and the Mars line is irrelevant.

Other commands:

```bash
python -m app.cli verify examples/sample_claim.json --json            # verdict only
python -m app.cli gate examples/sample_rag.json --policy rag_citation_gate --json
python -m app.cli audit examples/sample_claim.json --out reports/audit  # audit.md + audit.json
python -m app.cli policies --json
```

## Usage

**HTTP API**

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

Endpoints: `GET /health`, `/sources`, `/policies`, `/history`; `POST /verify`, `/verify/batch`, `/gate`. A Dockerfile is included for the API.

**From Python**

```python
from app.services.gate import gate, gate_context
from app.models.claim import Claim
from app.models.evidence import Evidence

claim = Claim(text="Earth has one natural satellite.")
evidence = [Evidence(text="NASA confirms Earth has one natural satellite called the Moon.",
                     source="NASA", reliability=0.98)]

result = gate(claim, evidence, policy_id="agent_tool_gate", decompose=False)
if result.allowed():
    call_tool()

# or: raise unless the decision is ALLOW
with gate_context(claim, evidence, decompose=False):
    call_tool()
```

**RAG citations.** Send `answer` plus `citations[]` instead of `claim` plus `evidence` (see `examples/sample_rag.json`). The reasons say which citations supported or contradicted the answer.

**Golden suite in CI.** `examples/golden/suite.yaml` lists claims with their expected verdict and decision. `suite gate` fails if any result differs from the lockfile:

```bash
python -m app.cli suite run examples/golden/suite.yaml
python -m app.cli suite gate examples/golden/suite.yaml --lockfile examples/golden/suite.lock.json
```

**Streamlit demo.** Run `streamlit run streamlit_app.py`. It includes buttons to export an audit.

## Policies

A policy maps verdict and confidence to a decision. Three presets live in `app/policies/`:

| Preset | Minimum confidence for ALLOW | Intended use |
| --- | --- | --- |
| `agent_tool_gate` | 0.55 | Before an agent tool with side effects |
| `rag_citation_gate` | 0.65 | Does the citation support the answer? |
| `caption_gate` | 0.45 | Image caption checks |

Risk tags can tighten a decision. For example, `payment` or `delete` can force `BLOCK`, and `pii` can turn `ALLOW` into `REVIEW`. You can override a preset in YAML, in the request body, or with environment variables:

| Variable | Default | Effect |
| --- | --- | --- |
| `TRUTHGRAPH_POLICY` | `agent_tool_gate` | Default preset |
| `TRUTHGRAPH_POLICY_MIN_CONFIDENCE_ALLOW` | from preset | Override the ALLOW threshold |
| `TRUTHGRAPH_POLICY_BLOCK_ON_CONTRADICTED` | from preset | Block contradicted claims |
| `TRUTHGRAPH_POLICY_BLOCK_RISK_TAGS` | from preset | Comma-separated tags that force BLOCK |
| `TRUTHGRAPH_DECOMPOSE` | `1` | Split compound claims into sub-claims |
| `TRUTHGRAPH_SEMANTIC` | `0` | Blend in TF-IDF cosine similarity |
| `TRUTHGRAPH_HISTORY` | `0` | Store results in SQLite |

## How it works

Compound claims are optionally split into sub-claims. Each piece of evidence is scored for relevance by keyword overlap (optionally blended with TF-IDF similarity), checked for negation and number mismatches, and weighted by its `reliability`. Support and contradiction scores give the verdict and confidence. The policy then turns those into a decision. The `/verify` response keeps the field names used by [VisionEval](https://github.com/nishanttyagi28/VisionEval) (`claim`, `verdict`, `confidence`, `supporting_evidence`, `contradicting_evidence`, `matched_keywords`).

## Limitations

- Confidence measures how strongly the submitted evidence supports or contradicts the claim. It is not a calibrated probability that the claim is true.
- Matching is lexical by default, so paraphrases with little word overlap can come back as `insufficient`. The optional semantic mode is TF-IDF, not embeddings.
- The policy thresholds are heuristics. Tune them for your own use.
- It doesn't fetch evidence and can't tell whether your evidence is correct.

## Development

```bash
pip install -r requirements.txt
python -m pytest -q
```

CI runs the tests on Python 3.11 and 3.12, plus the golden suite gate. Release notes are in [CHANGELOG.md](CHANGELOG.md).

## License

No license file has been added to this repository yet.
