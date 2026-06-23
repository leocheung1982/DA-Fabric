"""Evaluation — run experiments, view result tables and figures."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ui.pages._utils import (
    FIGURES_DIR,
    PROJECT_ROOT,
    RESULTS_DIR,
    get_service,
    load_results_csv,
    run_experiment_script,
    summarize_results_csv,
)

st.title("Evaluation & Experiments")
st.caption("Paper evaluation metrics: matching, views, orchestration, proactive, ablation")

EXPERIMENTS = {
    "Matching": "experiments/run_matching_eval.py",
    "View Construction": "experiments/run_view_eval.py",
    "Orchestration": "experiments/run_orchestration_eval.py",
    "Proactive Delivery": "experiments/run_proactive_eval.py",
    "Ablation": "experiments/run_ablation_eval.py",
    "Generate Figures": "experiments/plot_results.py",
}

st.subheader("Run experiments")
cols = st.columns(3)
for i, (name, script) in enumerate(EXPERIMENTS.items()):
    with cols[i % 3]:
        if st.button(f"Run {name}", key=f"exp_{i}"):
            with st.spinner(f"Running {name}..."):
                ok, output = run_experiment_script(script)
            if ok:
                st.success(f"{name} complete")
                st.code(output[-800:] if len(output) > 800 else output)
            else:
                st.error(output[-800:] if output else "Experiment failed.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Matching", "Views", "Orchestration", "Proactive", "Ablation"]
)

with tab1:
    summary = summarize_results_csv("matching_results.csv", "method")
    detail = load_results_csv("matching_results.csv")
    if summary is not None:
        st.markdown("**Summary (mean @5)**")
        st.dataframe(summary, use_container_width=True, hide_index=True)
    if detail is not None:
        with st.expander("Per-demand detail"):
            st.dataframe(detail.head(50), use_container_width=True, hide_index=True)
    else:
        st.info("Run matching evaluation to populate results/matching_results.csv.")

with tab2:
    df = load_results_csv("view_results.csv")
    if df is not None:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Run view evaluation to populate results/view_results.csv.")

with tab3:
    summary = summarize_results_csv("orchestration_results.csv", "method")
    detail = load_results_csv("orchestration_results.csv")
    if summary is not None:
        st.dataframe(summary, use_container_width=True, hide_index=True)
    if detail is not None:
        with st.expander("Per-demand detail"):
            st.dataframe(detail.head(50), use_container_width=True, hide_index=True)
    else:
        st.info("Run orchestration evaluation to populate results/orchestration_results.csv.")

with tab4:
    summary = summarize_results_csv("proactive_results.csv", "method")
    detail = load_results_csv("proactive_results.csv")
    if summary is not None:
        st.dataframe(summary, use_container_width=True, hide_index=True)
    if detail is not None:
        with st.expander("Event detail"):
            st.dataframe(detail.head(50), use_container_width=True, hide_index=True)
    else:
        st.info("Run proactive evaluation to populate results/proactive_results.csv.")

with tab5:
    df = load_results_csv("ablation_results.csv")
    if df is not None:
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Run ablation evaluation to populate results/ablation_results.csv.")

st.subheader("Generated figures")
FIGURE_STEMS = [
    "matching_metrics",
    "view_construction_latency",
    "orchestration_comparison",
    "proactive_delivery",
    "ablation_results",
]

if FIGURES_DIR.exists():
    found = False
    for stem in FIGURE_STEMS:
        png = FIGURES_DIR / f"{stem}.png"
        if png.exists():
            found = True
            st.markdown(f"**{stem.replace('_', ' ').title()}**")
            st.image(str(png), use_container_width=True)
    if not found:
        st.info("Run `python experiments/plot_results.py` to generate figures.")
else:
    st.info("No figures directory yet. Run plot_results.py after experiments.")

st.subheader("Feedback optimization")
service = get_service()
if st.button("Run matcher optimization"):
    snapshot = service.feedback.optimize()
    st.json(snapshot.model_dump())
st.json(service.feedback.summary())
