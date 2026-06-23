"""Proactive Delivery — simulate updates, triggers, and user feedback."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ui.pages._utils import (
    get_service,
    load_json,
    proactive_event_to_row,
    record_proactive_feedback,
)

st.title("Proactive Service Delivery")
st.caption("Subscription-triggered proactive data services")

service = get_service()
proactive = service.proactive
proactive.load_subscriptions()
proactive.load_resources()

st.metric("Subscription-enabled demands", len(proactive.subscription_demands))

tab_sim, tab_events, tab_hist = st.tabs(
    ["Simulate Update", "Delivery Events", "Historical Log"]
)

FEEDBACK_ACTIONS = ["viewed", "clicked", "adopted", "ignored", "rejected"]

with tab_sim:
    st.markdown(
        "Simulate a resource metadata update, evaluate subscription triggers, "
        "and deliver proactive notifications."
    )
    if st.button("Simulate resource update", type="primary"):
        update = proactive.simulate_resource_update()
        st.session_state.last_update = update
        candidates = proactive.check_triggers(update)
        delivered = [proactive.deliver(c) for c in candidates]
        proactive.save_events()
        st.session_state.last_delivered = delivered

    if "last_update" in st.session_state:
        st.subheader("Update event")
        st.json(st.session_state.last_update)

    if st.session_state.get("last_delivered"):
        st.subheader(f"Triggered deliveries ({len(st.session_state.last_delivered)})")
        st.dataframe(
            pd.DataFrame([proactive_event_to_row(e) for e in st.session_state.last_delivered]),
            use_container_width=True,
            hide_index=True,
        )

with tab_events:
    events = proactive.history[-20:][::-1]
    if not events:
        st.info("No delivery events in session. Simulate an update first.")
    else:
        for event in events:
            with st.expander(
                f"{event.event_id} — {event.demand_id} ({event.user_action or 'pending'})",
                expanded=False,
            ):
                st.json(event.model_dump(mode="json"))
                cols = st.columns(len(FEEDBACK_ACTIONS))
                for i, action in enumerate(FEEDBACK_ACTIONS):
                    if cols[i].button(action.capitalize(), key=f"fb_{event.event_id}_{action}"):
                        if record_proactive_feedback(service, event.event_id, action):
                            st.success(f"Recorded feedback: {action}")
                            st.rerun()
                        else:
                            st.error("Could not update event.")

        st.dataframe(
            pd.DataFrame([proactive_event_to_row(e) for e in events]),
            use_container_width=True,
            hide_index=True,
        )

with tab_hist:
    historical = load_json("proactive_events.json")
    st.metric("Persisted events", len(historical))
    if historical:
        hdf = pd.DataFrame(historical)
        display_cols = [
            c
            for c in [
                "event_id",
                "demand_id",
                "trigger_type",
                "target_application",
                "relevance_score",
                "user_action",
            ]
            if c in hdf.columns
        ]
        st.dataframe(hdf[display_cols].tail(30).iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.info("No persisted proactive events in data/proactive_events.json.")
