"""Resource Catalog — browse and inspect resource metadata."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from ui.pages._utils import get_service, resource_to_row

st.title("Resource Catalog")
st.caption("Resource metadata layer across platform and source nodes")

service = get_service()
store = service.metadata

node_types = ["All"] + store.platforms()
domains = ["All"] + store.domains()
entity_types = ["All"] + store.entity_types()

c1, c2, c3 = st.columns(3)
sel_node_type = c1.selectbox("Node type", node_types)
sel_domain = c2.selectbox("Business domain", domains)
sel_entity = c3.selectbox("Entity type", entity_types)

filtered = store.filter_resources(
    node_type=None if sel_node_type == "All" else sel_node_type,
    business_domain=None if sel_domain == "All" else sel_domain,
    entity_type=None if sel_entity == "All" else sel_entity,
)

st.metric("Matching resources", len(filtered))

if not filtered:
    st.warning("No resources match the selected filters.")
    st.stop()

df = pd.DataFrame([resource_to_row(r) for r in filtered])
st.dataframe(df, use_container_width=True, height=420, hide_index=True)

selected_id = st.selectbox(
    "Inspect resource",
    [r.resource_id for r in filtered],
    format_func=lambda rid: next(r.name for r in filtered if r.resource_id == rid),
)

resource = store.get(selected_id)
if resource:
    st.subheader(resource.name)
    st.write(resource.description)

    m1, m2, m3 = st.columns(3)
    m1.metric("Quality score", f"{resource.quality_score:.2f}")
    m2.metric("Fields", len(resource.fields))
    m3.metric("Update frequency", resource.update_frequency)

    tab_fields, tab_json = st.tabs(["Fields & Indicators", "Full metadata"])
    with tab_fields:
        st.markdown("**Schema fields**")
        st.write(", ".join(resource.fields) if resource.fields else "—")
        st.markdown("**Indicators**")
        st.write(", ".join(resource.indicators) if resource.indicators else "—")
        st.markdown("**Keywords**")
        st.write(", ".join(resource.keywords) if resource.keywords else "—")
    with tab_json:
        st.json(resource.model_dump(mode="json"))
