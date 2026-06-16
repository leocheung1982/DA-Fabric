# DA-Fabric

DA-Fabric is a research prototype for the paper:

**From Passive Querying to Proactive Data Services: A Demand-Aware Data Fabric Framework for Multi-Platform Data Environments**

The prototype implements a demand-aware data fabric framework for multi-platform data environments. It includes a fabric control and orchestration plane, simulated platform-side nodes, source-side nodes, application-side nodes, a demand metadata model, semantic supply-demand matching, virtual view construction, cross-node orchestration, proactive delivery simulation, and evaluation scripts.

## Overview

DA-Fabric is designed for research and reproducibility. It is not a production system. The prototype uses synthetic metadata and synthetic demand scenarios based on an enterprise regulation setting.

The framework supports:

- resource metadata management;
- demand metadata generation;
- semantic supply-demand matching;
- demand-driven virtual view construction;
- cross-node task orchestration;
- proactive service delivery simulation;
- ablation and scalability evaluation.

## Project Structure

```text
DA-Fabric/
├── core/              # Core framework components
├── data/              # Synthetic benchmark data
├── scripts/           # Data generation scripts
├── experiments/       # Evaluation scripts
├── results/           # Generated experimental results
├── figures/           # Generated plots
└── ui/                # Optional Streamlit demo
