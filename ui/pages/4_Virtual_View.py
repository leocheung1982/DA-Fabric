"""Virtual View — matching, view construction, and orchestrated execution."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ui.pages._utils import get_service, load_semantic_mappings

st.title("Virtual View Construction")
st.caption("Demand-driven virtual views and cross-node orchestration")

service = get_service()
demands = service.demands.list_demands()

if not demands:
    st.warning("No demands available. Generate or submit demands first.")
    st.stop()

sel_demand = st.selectbox(
    "Select demand",
    demands,
    format_func=lambda d: f"{d.demand_id} — {d.task}",
)
top_k = st.slider("Matching top-K", 3, 15, 8)

if "view_state" not in st.session_state:
    st.session_state.view_state = {}

run_match = st.button("Run semantic matching", type="primary")
run_build = st.button("Build virtual view")
run_execute = st.button("Simulate execution")

bucket = st.session_state.view_state.setdefault(sel_demand.demand_id, {})

if run_match or run_build or run_execute:
    bucket["matches"] = service.match_demand(sel_demand.demand_id, top_k=top_k)

matches = bucket.get("matches", [])

if run_match or matches:
    st.subheader("Ranked matching resources")
    if matches:
        mdf = pd.DataFrame(
            [
                {
                    "rank": m.rank,
                    "resource_id": m.resource_id,
                    "score": m.score,
                    "keyword": m.keyword_score,
                    "semantic": m.semantic_score,
                    "context": m.context_score,
                    "quality": m.quality_score,
                    "matched_fields": ", ".join(m.matched_fields),
                }
                for m in matches
            ]
        )
        st.dataframe(mdf, use_container_width=True, hide_index=True)
    elif run_match:
        st.warning("No matches returned.")

view = None
if run_build or run_execute:
    if not matches:
        st.error("Run semantic matching first.")
    else:
        mappings = load_semantic_mappings()
        view = service.view_builder.build_from_demand(
            sel_demand,
            matches,
            service.metadata.list_resources(),
            mappings=mappings,
        )
        service._views[view.view_id] = view
        bucket["view"] = view

if bucket.get("view"):
    view = bucket["view"]

if view:
    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Construction time (ms)", f"{view.construction_time_ms:.1f}")
    c2.metric("Selected resources", len(view.selected_resources))
    c3.metric("Field mappings", len(view.field_mappings))

    tab_json, tab_plan, tab_exec = st.tabs(
        ["Virtual view JSON", "Execution plan", "Execution result"]
    )

    with tab_json:
        st.json(view.model_dump(mode="json"))

    with tab_plan:
        plan = view.execution_plan or {}
        st.markdown(f"**Mode:** {plan.get('execution_mode', '—')}")
        st.markdown(f"**Platform node:** {plan.get('platform_node_id', '—')}")
        tasks = plan.get("tasks", [])
        if tasks:
            tdf = pd.DataFrame(tasks)
            show_cols = [c for c in ["task_id", "node_id", "resource_id", "operation"] if c in tdf.columns]
            st.dataframe(tdf[show_cols], use_container_width=True, hide_index=True)
        node_groups = plan.get("node_groups", {})
        if node_groups:
            st.markdown("**Node groups**")
            st.json(node_groups)

    with tab_exec:
        if run_execute:
            result = service.orchestrator.execute_view(view)
            bucket["result"] = result
        result = bucket.get("result")
        if result:
            c1, c2, c3 = st.columns(3)
            c1.metric("Status", result.status)
            c2.metric("Latency (ms)", f"{result.latency_ms:.1f}")
            c3.metric("Invoked nodes", len(result.invoked_nodes))
            st.markdown("**Invoked resources**")
            st.write(", ".join(result.invoked_resources) or "—")
            st.json(result.model_dump(mode="json"))
        else:
            st.info("Click **Simulate execution** to run the orchestration plan.")
