"""Optional Streamlit demo for TruthGraph."""

from __future__ import annotations

import streamlit as st

from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.verifier import verify_claim

st.set_page_config(page_title="TruthGraph Demo", page_icon="🔎", layout="centered")
st.title("TruthGraph")
st.caption("Explainable claim verification against the evidence you provide.")

claim_text = st.text_area(
    "Claim",
    value="Earth has one natural satellite.",
    height=80,
)
evidence_text = st.text_area(
    "Evidence (one item for this demo)",
    value="NASA confirms that Earth has one natural satellite called the Moon.",
    height=100,
)
source = st.text_input("Source name", value="NASA")
reliability = st.slider("Caller reliability", 0.0, 1.0, 0.95, 0.01)
use_semantic = st.checkbox("Hybrid semantic scoring", value=False)
use_registry = st.checkbox("Use source reputation registry", value=False)
decompose = st.checkbox("Decompose claim", value=True)

if st.button("Verify", type="primary"):
    try:
        claim = Claim(text=claim_text.strip())
        evidence = [
            Evidence(
                text=evidence_text.strip(),
                source=source.strip() or "unknown",
                reliability=reliability,
            )
        ]
        if use_registry:
            from app.services.reputation import lookup_reputation

            evidence[0] = evidence[0].model_copy(
                update={"reliability": lookup_reputation(evidence[0].source, reliability)}
            )
        result = verify_claim(
            claim,
            evidence,
            use_semantic=use_semantic,
            use_registry=use_registry,
            decompose=decompose,
        )
        st.subheader(f"Verdict: {result.verdict}")
        st.metric("Confidence", f"{result.confidence:.3f}")
        st.write("Matched keywords:", ", ".join(result.matched_keywords) or "(none)")
        if result.reasons:
            st.markdown("**Reasons**")
            for reason in result.reasons:
                st.write(f"- {reason}")
        if result.subclaims:
            st.markdown("**Sub-claims**")
            st.json([s.model_dump() for s in result.subclaims])
        st.markdown("**Full dossier**")
        st.json(result.model_dump())
    except Exception as exc:  # noqa: BLE001 — demo UX
        st.error(str(exc))
