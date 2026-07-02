# GNN Buyer Simulation Design

**Date:** 2026-06-28
**Status:** Approved
**Approach:** B — OASIS-Style Agent Sim + GNN Valuation

## Purpose

Simulate heterogeneous buyer agents competing for Tokyo real estate properties. Each buyer has distinct preferences (budget, risk tolerance, life stage, construction preference, commute target). A Graph Neural Network propagates information across the buyer-property-neighborhood graph to discover market-consensus valuations. The output report compares GNN-derived prices with existing satei (hedonic comparable) and price-probability (Monte Carlo) analyses.

## Architecture

```
MLIT Providers (REINFOLIB/Hazard) -> Feature Extractor -> Property Nodes
                                                              |
Buyer Profiles (generated) -> Buyer Nodes -> AgentGraph (bipartite + spatial)
                                                              |
                                              GNN Message Passing (PyTorch)
                                                              |
                                              Environment Step Loop
                                              (observe -> bid -> resolve -> update)
                                                              |
                                              Report Generator
                                              (GNN price vs satei vs Monte Carlo)
```

## Components

### 1. Feature Extractor

Extracts a fixed-length feature vector per property from DB + MLIT signals (~20 dims, normalized [0,1]).

### 2. Buyer Agent

Each buyer is a frozen dataclass with: budget_yen, risk_tolerance, life_stage, construction_pref, commute_target, hazard_sensitivity, yield_target. Scoring is pure math (no LLM).

### 3. Agent Graph

Networkx graph with three edge types: buyer->property (INTEREST), property->property (COMPARABLE), buyer->buyer (SIMILAR).

### 4. GNN Model

2-layer Graph Attention Network in raw PyTorch. Heterogeneous message passing across edge types. Outputs: gnn_valuation_yen per property, bid_score per buyer-property pair.

### 5. Environment

OASIS-inspired step loop: reset -> step (GNN forward, observe, bid, resolve, update graph) -> converge.

### 6. Report Generator

Compares GNN valuation with satei and price-probability. Includes buyer segmentation, bid histogram, hazard impact analysis.

## File Layout

```
domain/buyer_sim/
  __init__.py
  models.py
  feature_extractor.py
  buyer_agent.py
  agent_graph.py
  gnn.py
  environment.py
  report.py
  buyer_generator.py

services/buyer_simulation.py
api/buyer_simulation.py
frontend/src/pages/BuyerSimPage.tsx
```

## Domain Purity

domain/buyer_sim/ is side-effect free. All I/O in services/buyer_simulation.py.
