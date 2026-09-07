"""Optional Streamlit demo for TruthGraph — verify + gate + audit export."""

from __future__ import annotations

import streamlit as st

from app.models.claim import Claim
from app.models.evidence import Evidence
from app.services.audit import export_audit, render_audit_markdown, build_audit_payload
from app.services.gate import gate
from app.services.policy import list_presets

st.set_page_config(page_title="TruthGraph Gate", page_icon="🛡️", layout="centered")
st.title("TruthGraph")
st.caption(
    "Deterministic evidence gate for AI agents & RAG — ALLOW / REVIEW / BLOCK "
    "with an inspectable dossier. Not an LLM judge."
)

presets = list_presets()
policy_id = st.selectbox("Policy", list(presets.keys()), index=0)
claim_text = st.text_area(
    "Claim / answer",
    value="Earth has one natural satellite.",
    height=80,
)
evidence_text = st.text_area(
    "Evidence / citation (one item for this demo)",
    value="NASA confirms that Earth has one natural satellite called the Moon.",
    height=100,
)
source = st.text_input("Source name", value="NASA")
reliability = st.slider("Caller reliability", 0.0, 1.0, 0.95, 0.01)
use_semantic = st.checkbox("Hybrid semantic scoring", value=False)
use_registry = st.checkbox("Use source reputation registry", value=False)
decompose = st.checkbox("Decompose claim", value=False)
risk_tags_raw = st.text_input("Risk tags (comma-separated)", value="")

col1, col2 = st.columns(2)
run_gate = col1.button("Gate (verify + decide)", type="primary")
run_verify_only = col2.button("Verify only")

if run_gate or run_verify_only:
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
        risk_tags = [t.strip() for t in risk_tags_raw.split(",") if t.strip()]
        gr = gate(
            claim,
            evidence,
            policy_id=policy_id,
            risk_tags=risk_tags,
            use_semantic=use_semantic,
            use_registry=use_registry,
            decompose=decompose,
        )
        if run_gate:
            st.subheader(f"Decision: {gr.decision}")
            st.write(f"Policy: `{gr.policy_id}`")
            for reason in gr.policy_reasons:
                st.write(f"- {reason}")
        st.metric("Verdict", gr.verdict)
        st.metric("Confidence", f"{gr.confidence:.3f}")
        st.write("Matched keywords:", ", ".join(gr.verification.matched_keywords) or "(none)")
        if gr.reasons:
            st.markdown("**Reasons**")
            for reason in gr.reasons[:20]:
                st.write(f"- {reason}")
        st.markdown("**Full dossier**")
        st.json(gr.verification.model_dump())

        audit_payload = build_audit_payload(gr.verification, decision=gr.policy)
        md = render_audit_markdown(audit_payload)
        st.download_button(
            "Export audit (Markdown)",
            data=md,
            file_name="truthgraph_audit.md",
            mime="text/markdown",
        )
        st.download_button(
            "Export audit (JSON)",
            data=__import__("json").dumps(audit_payload, indent=2),
            file_name="truthgraph_audit.json",
            mime="application/json",
        )
        if st.button("Also write reports/streamlit_audit.*"):
            paths = export_audit(
                gr.verification,
                "reports",
                basename="streamlit_audit",
                decision=gr.policy,
            )
            st.success(f"Wrote {paths['json']} and {paths['markdown']}")
    except Exception as exc:  # noqa: BLE001 — demo UX
        st.error(str(exc))
