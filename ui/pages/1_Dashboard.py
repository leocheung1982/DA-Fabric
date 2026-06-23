"""Dashboard — system overview and recent activity."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ui.pages._utils import (
    demand_to_row,
    get_service,
    load_json,
    proactive_event_to_row,
)

st.title("Dashboard")
st.caption("Fabric control plane status and recent activity")

service = get_service()
status = service.get_status()
proactive_events = service.proactive.history

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Nodes", status["nodes"])
c2.metric("Resources", status["resources"])
c3.metric("Demands", status["demands"])
c4.metric("Virtual Views", len(service._views))
c5.metric("Proactive Events", len(proactive_events))

st.divider()

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Recent Demands")
    demands = service.demands.list_demands()[:10]
    if demands:
        st.dataframe(
            pd.DataFrame([demand_to_row(d) for d in demands]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No demands loaded. Run `python scripts/generate_synthetic_data.py`.")

with col_b:
    st.subheader("Recent Proactive Events")
    if proactive_events:
        recent = proactive_events[-10:][::-1]
        st.dataframe(
            pd.DataFrame([proactive_event_to_row(e) for e in recent]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        historical = load_json("proactive_events.json")
        if historical:
            hdf = pd.DataFrame(historical).tail(10).iloc[::-1]
            display_cols = [
                c
                for c in [
                    "event_id",
                    "demand_id",
                    "trigger_type",
                    "relevance_score",
                    "user_action",
                ]
                if c in hdf.columns
            ]
            st.dataframe(hdf[display_cols], use_container_width=True, hide_index=True)
        else:
            st.info("No proactive events yet. Use the Proactive Delivery page to simulate.")

st.subheader("Node Distribution")
st.json(status["nodes_by_type"])
