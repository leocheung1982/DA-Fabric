# DA-Fabric

**From Passive Querying to Proactive Data Services: A Demand-Aware Data Fabric Framework for Multi-Platform Data Environments**

DA-Fabric is a research prototype that demonstrates a demand-aware data fabric for multi-platform data environments. It supports reproducible experiments, interactive demos, and optional REST access — but it is **not** intended for production deployment.

The prototype simulates an enterprise regulation scenario: platform-side, source-side, and application-side fabric nodes exchange metadata through a unified control plane, match application demands to distributed resources, construct virtual views, orchestrate cross-node tasks, and deliver proactive data services driven by subscriptions and feedback.

---

## Project Overview

DA-Fabric implements the full paper workflow in software:

1. **Register fabric nodes** and expose their capabilities.
2. **Catalog resource metadata** across heterogeneous platforms.
3. **Accept demand metadata** from application-side consumers.
4. **Match demands to resources** using keyword, semantic, context, and quality signals.
5. **Build virtual views** that federate selected resources and field mappings.
6. **Orchestrate execution** across platform, source, and application nodes.
7. **Deliver proactive notifications** when subscribed resources change.
8. **Collect feedback** and adjust matching behavior over time.

All persistent state is stored as JSON under `data/`. Evaluation outputs are written to `results/` as CSV files and publication-ready figures.

---

## Mapping to the Paper Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│              Fabric Control & Orchestration Plane                   │
│  Registry │ Metadata │ Demands │ Matcher │ View Builder            │
│  Orchestrator │ Proactive Service │ Feedback Optimizer             │
└──────────────────────────────────────────────────────────────────┘
         │                      │                      │
   ┌─────▼─────┐          ┌─────▼─────┐          ┌─────▼─────┐
   │ Platform  │          │  Source   │          │Application│
   │   Nodes   │          │   Nodes   │          │   Nodes   │
   └───────────┘          └───────────┘          └───────────┘
         │                      │                      │
         └──────────────────────┼──────────────────────┘
                                │
                  Resource & Application Layer
                  (synthetic JSON metadata catalog)
```

| Paper concept | Implementation | Module |
|---------------|----------------|--------|
| Fabric node registration | Platform / source / application nodes | `core/registry.py`, `nodes/` |
| Resource metadata catalog | Synthetic multi-platform catalog | `core/metadata_store.py` |
| Demand metadata submission | Application-side demand objects | `core/demand_manager.py` |
| Semantic supply–demand matching | Weighted keyword + semantic + context + quality scoring | `core/semantic_matcher.py` |
| Virtual view construction | Resource selection, field mapping, execution plan | `core/view_builder.py` |
| Cross-node orchestration | Deterministic task simulation and latency model | `core/orchestrator.py` |
| Proactive data services | Subscription triggers on resource updates | `core/proactive_service.py` |
| Feedback optimization loop | Resource boosts and mapping confidence updates | `core/feedback_optimizer.py` |
| Unified demo / API facade | Shared service layer for UI and REST | `backend/service_layer.py` |

### Evaluation mapping (Section IV)

| Experiment script | Paper section | Compared methods / settings |
|-------------------|---------------|----------------------------|
| `run_matching_eval.py` | IV-A | KW-Catalog, Semantic-Only, Supply-Fabric, DA-Fabric, DA-Fabric+Feedback |
| `run_view_eval.py` | IV-B | Resource scales: 100, 300, 500, 1000, 3000, 5000 |
| `run_orchestration_eval.py` | IV-C | Supply-Fabric vs DA-Fabric |
| `run_proactive_eval.py` | IV-D | Subscription-Only vs DA-Proactive |
| `run_ablation_eval.py` | IV-E | Full DA-Fabric and component ablations |

---

## Requirements

- Python 3.11+
- Dependencies in `requirements.txt`

Optional neural embedding baseline:

```bash
pip install sentence-transformers
```

---

## Installation

```bash
cd datafabric-frw
pip install -r requirements.txt
```

---

## Generating Synthetic Data

Generate the full enterprise regulation dataset:

```bash
python scripts/generate_synthetic_data.py
```

This creates JSON files under `data/`:

| File | Contents |
|------|----------|
| `nodes.json` | 6 platform, 12 source, 4 application fabric nodes |
| `resources.json` | 500 synthetic resource metadata records |
| `demands.json` | 100 application demand scenarios |
| `semantic_mappings.json` | 1000 auxiliary term mappings |
| `ground_truth.json` | Relevance labels (3–8 relevant resources per demand) |
| `feedback_events.json` | Empty feedback log (populated during demo use) |
| `proactive_events.json` | Empty proactive event log |

Alternative initialization:

```bash
python scripts/initialize_demo.py
# or
python run_demo.py --init
```

Reset generated data:

```bash
python scripts/reset_data.py
```

---

## Running the Streamlit UI

```bash
streamlit run ui/streamlit_app.py
```

Or:

```bash
python run_demo.py --ui
```

### UI pages

| Page | Purpose |
|------|---------|
| **Dashboard** | Counts of nodes, resources, demands, views, proactive events; recent activity |
| **Resource Catalog** | Browse/filter resources by node type, business domain, entity type |
| **Demand Submission** | Create `DemandMetadata`, save to `data/demands.json`, run matching |
| **Virtual View** | Match, build view, inspect execution plan, simulate orchestration |
| **Proactive Delivery** | Simulate resource updates, triggers, deliveries, and user feedback |
| **Evaluation** | Run experiments, inspect CSV results, view generated figures |

---

## Running the FastAPI Backend

The REST API is optional for experiments but provides programmatic access to the same core workflow.

```bash
uvicorn backend.main:app --reload
```

Or:

```bash
python run_demo.py --api
```

Interactive API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service metadata and live status |
| GET | `/health` | Health check |
| GET | `/nodes` | List registered fabric nodes |
| POST | `/nodes/register` | Register a new node |
| GET | `/resources` | List resource metadata (filterable) |
| GET | `/demands` | List demands |
| POST | `/demands` | Submit a new demand |
| POST | `/match/{demand_id}` | Run semantic matching |
| POST | `/views/{demand_id}` | Build a virtual view |
| POST | `/execute/{view_id}` | Simulate view execution |
| POST | `/proactive/simulate` | Simulate proactive delivery pipeline |
| POST | `/feedback` | Record user feedback |

Example:

```bash
curl http://localhost:8000/
curl http://localhost:8000/demands
curl -X POST http://localhost:8000/match/dem-00001 -H "Content-Type: application/json" -d "{\"top_k\": 5}"
```

---

## Running Experiments

Run each evaluation from the project root:

```bash
python experiments/run_matching_eval.py
python experiments/run_view_eval.py
python experiments/run_orchestration_eval.py
python experiments/run_proactive_eval.py
python experiments/run_ablation_eval.py
python experiments/plot_results.py
```

Run all experiments and figures at once:

```bash
python run_demo.py --experiments
```

Each script prints a summary table to the console and writes CSV output under `results/`.

### Result files

| Script | Output CSV | Metrics |
|--------|------------|---------|
| `run_matching_eval.py` | `matching_results.csv` | Precision@5, Recall@5, NDCG@5, MRR |
| `run_view_eval.py` | `view_results.csv` | Avg matching time, view construction time, selected resource count |
| `run_orchestration_eval.py` | `orchestration_results.csv` | Invoked nodes/resources, redundant ratio, end-to-end latency |
| `run_proactive_eval.py` | `proactive_results.csv` | Delivery precision, adoption rate, ignored rate, time-to-awareness |
| `run_ablation_eval.py` | `ablation_results.csv` | P@5, NDCG@5, invoked nodes, delivery precision |

Generate publication figures (PNG + PDF):

```bash
python experiments/plot_results.py
```

Figures are saved to `results/figures/`:

- `matching_metrics.png` / `.pdf`
- `view_construction_latency.png` / `.pdf`
- `orchestration_comparison.png` / `.pdf`
- `proactive_delivery.png` / `.pdf`
- `ablation_results.png` / `.pdf`

---

## Interpreting Results

### Matching evaluation (`matching_results.csv`)

Compares baseline catalog/matching approaches against DA-Fabric.

- **Precision@5** — fraction of top-5 retrieved resources that are ground-truth relevant (relevance ≥ 0.6).
- **Recall@5** — fraction of all relevant resources captured in the top-5 set.
- **NDCG@5** — ranking quality with graded relevance; higher when more relevant items appear earlier.
- **MRR** — mean reciprocal rank of the first relevant result.

Higher values indicate better supply–demand alignment. DA-Fabric+Feedback should improve over DA-Fabric once feedback events accumulate in `data/feedback_events.json`.

### View construction (`view_results.csv`)

Measures scalability as the resource catalog grows (100 → 5000 resources).

- **avg_matching_time_ms** — time to rank candidate resources for a demand.
- **avg_view_construction_time_ms** — time to select resources, map fields, and build the execution plan.
- **avg_selected_resource_count** — number of resources included in each virtual view (capped at 8).

Expect matching time to grow with catalog size; view construction should remain comparatively stable.

### Orchestration (`orchestration_results.csv`)

Compares supply-side-only orchestration with demand-aware orchestration.

- **invoked_nodes** — distinct fabric nodes touched during execution.
- **invoked_resources** — resources materialized for the view.
- **redundant_invocation_ratio** — share of invoked resources not needed for ground-truth relevance.
- **end_to_end_latency_ms** — simulated total orchestration latency.

Lower redundant ratio and latency with comparable coverage indicates more efficient orchestration.

### Proactive delivery (`proactive_results.csv`)

Compares naive subscription triggers with demand-aware proactive filtering.

- **delivery_precision** — fraction of deliveries whose updated resource is ground-truth relevant.
- **adoption_rate** — fraction of deliveries adopted by the simulated user.
- **ignored_rate** — fraction ignored or rejected.
- **time_to_awareness_ms** — simulated notification latency.

DA-Proactive should produce fewer but more relevant deliveries than Subscription-Only.

### Ablation study (`ablation_results.csv`)

Measures the contribution of individual DA-Fabric components.

- Removing **semantic mapping**, **context**, **feedback**, or **application-side nodes** typically reduces matching quality and/or increases orchestration overhead.
- Compare each ablated row against **Full DA-Fabric** to quantify component impact.

---

## Project Structure

```
datafabric-frw/
├── README.md
├── requirements.txt
├── run_demo.py                 # Launcher for init, UI, API, experiments
├── backend/
│   ├── main.py                 # FastAPI application entry
│   ├── api_routes.py           # REST endpoints
│   ├── service_layer.py        # Unified facade for UI/API
│   └── storage.py              # JSON persistence helper
├── core/
│   ├── models.py               # Pydantic domain models
│   ├── registry.py             # Node registry
│   ├── metadata_store.py       # Resource catalog
│   ├── demand_manager.py       # Demand lifecycle
│   ├── semantic_matcher.py       # Matching engine and baselines
│   ├── view_builder.py         # Virtual view construction
│   ├── orchestrator.py         # Cross-node orchestration
│   ├── proactive_service.py      # Proactive delivery simulation
│   └── feedback_optimizer.py   # Feedback loop
├── nodes/
│   ├── base_node.py
│   ├── platform_node.py
│   ├── source_node.py
│   └── application_node.py
├── data/                       # JSON seed data and runtime logs
├── scripts/
│   ├── generate_synthetic_data.py
│   ├── initialize_demo.py
│   └── reset_data.py
├── experiments/
│   ├── _utils.py               # Shared metrics and loaders
│   ├── run_matching_eval.py
│   ├── run_view_eval.py
│   ├── run_orchestration_eval.py
│   ├── run_proactive_eval.py
│   ├── run_ablation_eval.py
│   └── plot_results.py
├── results/                    # CSV outputs and figures/
└── ui/
    ├── streamlit_app.py        # Streamlit entry point
    └── pages/                  # Multi-page demo UI
```

---

## Limitations

This repository is a **research prototype**, not a production data fabric.

- **Simulated data only** — all resources, demands, and executions are synthetic JSON metadata; no live databases or real regulatory systems are connected.
- **Simulated latency and orchestration** — node execution times and cross-platform federation are modeled deterministically, not measured on real infrastructure.
- **Default semantic matcher** — TF-IDF cosine similarity is used by default; neural embeddings require optional `sentence-transformers` installation.
- **In-memory views** — virtual views built via the API exist in the service session until the process restarts; they are not persisted as standalone artifacts.
- **Single-process demo** — no clustering, authentication, authorization, or multi-tenant isolation.
- **Feedback effects depend on usage** — DA-Fabric+Feedback and ablation results reflect accumulated feedback; a freshly generated dataset may show little or no feedback benefit until events are recorded through the UI or API.
- **Ground truth is synthetic** — evaluation metrics measure alignment with generated labels, which approximate but do not validate real-world regulatory matching quality.

Use this codebase to reproduce paper experiments, demonstrate the framework architecture, and extend the research — not as a drop-in enterprise integration platform.

---

## Citation

If you use this prototype in your research, please cite the associated paper:

> *From Passive Querying to Proactive Data Services: A Demand-Aware Data Fabric Framework for Multi-Platform Data Environments*

---

## License

Research prototype — for academic evaluation purposes.
