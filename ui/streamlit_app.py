"""
DA-Fabric Streamlit Demo UI.

Research prototype for demand-aware data fabric across multi-platform
data environments. Run from project root:

    streamlit run ui/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ui.pages._utils import PAPER_TITLE, get_service

st.set_page_config(
    page_title="DA-Fabric",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("DA-Fabric Research Prototype")
st.caption(PAPER_TITLE)

st.markdown(
    """
    This demo illustrates the **demand-aware data fabric** framework:

    1. **Resource catalog** — federated metadata across platform and source nodes  
    2. **Demand submission** — application-side demand metadata  
    3. **Semantic matching** — supply–demand alignment with context and quality signals  
    4. **Virtual views** — demand-driven view construction and orchestration  
    5. **Proactive delivery** — subscription-triggered data services  
    6. **Evaluation** — reproducible experiment metrics from the paper  

    Use the sidebar to navigate each component.
    """
)

service = get_service()
status = service.get_status()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Fabric Nodes", status["nodes"])
c2.metric("Resources", status["resources"])
c3.metric("Demands", status["demands"])
c4.metric("Matcher", status["matcher_method"])

st.info(
    "Initialize synthetic data with `python scripts/generate_synthetic_data.py`. "
    "Run experiments via the **Evaluation** page or `python run_demo.py --experiments`."
)
