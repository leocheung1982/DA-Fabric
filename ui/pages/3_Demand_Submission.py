"""Demand Submission — create demands and run semantic matching."""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from core.models import DemandMetadata, DemandPriority
from ui.pages._utils import demand_to_row, get_service

st.title("Demand Submission")
st.caption("Application-side demand metadata for the fabric control plane")

service = get_service()
store = service.metadata

tab_list, tab_submit, tab_match = st.tabs(
    ["Existing Demands", "Submit New Demand", "Ranked Matching"]
)

with tab_list:
    demands = service.demands.list_demands()
    st.metric("Total demands", len(demands))
    if demands:
        st.dataframe(
            pd.DataFrame([demand_to_row(d) for d in demands]),
            use_container_width=True,
            hide_index=True,
        )

with tab_submit:
    domains = store.domains()
    entity_types = store.entity_types()
    all_fields = sorted({f for r in store.list_resources() for f in r.fields})

    with st.form("demand_form", clear_on_submit=False):
        role = st.text_input("Role", "analyst")
        application = st.text_input("Application", "Regulatory Enforcement Portal")
        task = st.text_input("Task", "Query enterprise compliance profile")
        object_type = st.selectbox("Object type", entity_types or ["enterprise"])
        object_id = st.text_input("Object ID", "enterprise-demo-001")
        indicators = st.multiselect("Indicators", all_fields, default=all_fields[:4])
        c1, c2 = st.columns(2)
        time_start = c1.date_input("Time range start", value=date.today().replace(day=1))
        time_end = c2.date_input("Time range end", value=date.today())
        output_format = st.selectbox(
            "Output format", ["json", "csv", "parquet", "dashboard", "api"]
        )
        priority = st.selectbox("Priority", [p.value for p in DemandPriority])
        st.markdown("**Subscription (proactive delivery)**")
        sub_enabled = st.checkbox("Enable subscription", value=False)
        sub_channel = st.selectbox("Channel", ["push", "email", "webhook"])
        sub_frequency = st.selectbox("Frequency", ["realtime", "hourly", "daily", "weekly"])
        submitted = st.form_submit_button("Save demand", type="primary")

    if submitted:
        if not indicators:
            st.error("Select at least one indicator.")
        else:
            demand = DemandMetadata(
                role=role,
                application=application,
                task=task,
                object_type=object_type,
                object_id=object_id,
                indicators=indicators,
                conditions={
                    "business_domains": [object_type] if object_type in domains else domains[:1],
                    "description": f"UI-submitted demand for {object_type}",
                },
                time_range={"start": str(time_start), "end": str(time_end)},
                output_format=output_format,
                priority=DemandPriority(priority),
                subscription={
                    "enabled": sub_enabled,
                    "channel": sub_channel,
                    "frequency": sub_frequency,
                },
            )
            saved = service.submit_demand(demand)
            service.proactive.load_subscriptions()
            st.success(f"Demand saved to data/demands.json: `{saved.demand_id}`")
            st.json(saved.model_dump(mode="json"))

with tab_match:
    demand_ids = [d.demand_id for d in service.demands.list_demands()]
    if not demand_ids:
        st.info("Submit or generate demands first.")
    else:
        sel_id = st.selectbox("Select demand", demand_ids)
        top_k = st.slider("Top-K", 1, 10, 5)
        if st.button("Generate ranked matching resources", type="primary"):
            matches = service.match_demand(sel_id, top_k=top_k)
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
                            "reason": m.reason,
                        }
                        for m in matches
                    ]
                )
                st.dataframe(mdf, use_container_width=True, hide_index=True)
            else:
                st.warning("No matching resources found.")
