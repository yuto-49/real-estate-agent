# Business AI Implementation Platform - Skeleton Project

Date: 2026-03-22  
Baseline repo: `real-estate-agent` (FastAPI + React + multi-agent simulation + MiroFish pipeline)

## 1) Current Application Summary (What You Already Have)

This codebase is already a strong simulation platform with:

- A FastAPI backend (`main.py`, `api/*`) with async DB and background jobs.
- A React + TypeScript frontend (`frontend/src/*`) with simulation, reporting, chat, and profile workflows.
- Multi-agent orchestration (`agent/*`) with role-specific prompts, tool ACL, and tool-call traces.
- Simulation engines (`services/negotiation_simulator.py`, `services/batch_simulator.py`) that run repeated rounds and scenario variants.
- Intelligence pipeline (`intelligence/seed_assembly.py`, `intelligence/mirofish_client.py`, `api/reports.py`) that assembles context, runs simulation, and stores report outputs.
- Event-driven observability (`DomainEvent`, correlation IDs, structured logging, Redis pub/sub, metrics).

In short: the real-estate app already has the exact architecture needed for a corporate AI implementation simulator; only the domain model and simulation logic need to be retargeted.

## 2) Target Product Definition

Build a **Business AI Implementation Platform** that simulates how a company decides, pilots, and scales AI initiatives.

Core output:

- Priority Matrix of AI use cases (value vs effort vs risk vs adoption).
- Friction Map by stakeholder group and department.
- Simulated ROI with confidence ranges over time.
- Rollout plan with phase gates (Pilot -> Scale -> Standardize).

## 3) Domain Shift: Real Estate -> Business Value Chain

Replace the domain ontology from property negotiation to enterprise operations.

### 3.1 Required Ontology Entities

- `Company`
- `Department`
- `Role`
- `Process`
- `Bottleneck`
- `KPI`
- `AIUseCase`
- `AITool`
- `DataSource`
- `Constraint` (budget, legal, security, talent)
- `ImplementationPhase`
- `Risk`
- `Decision`
- `Outcome`

### 3.2 Required Graph Relationships

- `Department OWNS Process`
- `Process HAS_BOTTLENECK Bottleneck`
- `Bottleneck IMPACTS KPI`
- `AIUseCase TARGETS Bottleneck`
- `AITool ENABLES AIUseCase`
- `AIUseCase REQUIRES DataSource`
- `Constraint BLOCKS AIUseCase`
- `Decision MOVES_TO ImplementationPhase`
- `ImplementationPhase CHANGES KPI`
- `Outcome VALIDATES Decision`

### 3.3 Baseline Code Mapping

- `intelligence/seed_assembly.py` -> assemble business context pack (annual report, org chart, pain points, KPI baselines).
- `intelligence/mirofish_client.py` -> run corporate implementation simulation.
- `services/negotiation_simulator.py` -> proposal-feedback loop simulator.
- `services/scenario_variants.py` -> rollout scenarios (aggressive, balanced, conservative, compliance-first, cost-first).
- `intelligence/report_parser.py` -> parse implementation strategy outputs.

## 4) Persona System for Strategic Deliberation

Replace buyer/seller/broker with stakeholder personas:

- Skeptical CFO (ROI and budget risk)
- Visionary CTO (architecture and scalability)
- Frontline Manager (workflow reality and morale)
- Security/Legal Officer (compliance and privacy)
- Change Consultant (adoption and SOP redesign)

Each persona should include:

- `primary_goal`
- `decision_power` (advisory, veto, budget owner)
- `technical_skill_level`
- `risk_tolerance`
- `success_metrics`
- `hard_constraints`
- `trigger_conditions` (when they challenge or support proposals)

## 5) Simulation Logic (Proposal-Feedback Loop)

Shift from free-form “commenting” to structured rounds:

1. Proposal (owner persona proposes an AI use case)
2. Challenge (finance, legal, technical objections)
3. Revision (proposal updated with mitigations)
4. Feasibility vote (implement / pilot / reject / defer)
5. Monthly timestep progression (impact on KPIs, adoption, costs)

Stop conditions:

- Consensus reached
- Risk threshold exceeded
- Budget exhausted
- Max rounds reached

## 6) Additional Aspects To Consider (Beyond the Original AI Suggestion)

These are critical for realistic enterprise simulation quality:

- **Data readiness score**: AI projects fail if source systems are low quality or siloed.
- **Integration complexity**: ERP/CRM/legacy dependencies often dominate delivery timelines.
- **Human-in-the-loop policy**: identify decisions that must remain human-approved.
- **Security and privacy gates**: PII handling, data residency, model access controls.
- **Model governance lifecycle**: versioning, drift monitoring, rollback criteria.
- **Change management mechanics**: training load, SOP rewrites, manager sponsorship.
- **Adoption curve modeling**: value is delayed if frontline adoption is weak.
- **Cost governance (FinOps)**: token, compute, storage, and support costs by phase.
- **Vendor lock-in and portability risk**: optionality score for architecture decisions.
- **Incident and failure playbooks**: degraded mode, fallback workflows, escalation.
- **Regulatory variance by region/industry**: policy checks per business unit.
- **Program sequencing constraints**: capacity planning across teams and quarters.

## 7) Proposed Project Skeleton

```text
business-ai-platform/
  backend/
    api/
      implementation.py
      batch_implementation.py
      reports.py
      personas.py
      graph.py
    agents/
      stakeholder_base.py
      cfo_agent.py
      cto_agent.py
      frontline_manager_agent.py
      legal_security_agent.py
      change_consultant_agent.py
      persona_template.py
      tool_acl.py
      prompts.py
    graph/
      ontology_business_ai.json
      ontology_extractor.py
      graph_builder.py
    simulation/
      implementation_simulator.py
      proposal_engine.py
      consensus_scoring.py
      timestep_engine.py
      scenario_variants.py
    intelligence/
      business_seed_assembly.py
      mirofish_business_client.py
      report_parser.py
      templates/
        implementation_rules.md
        decision_framework.md
    services/
      roi_model.py
      adoption_model.py
      risk_model.py
      governance_checks.py
      event_store.py
      pubsub.py
      metrics.py
    db/
      models.py
      database.py
    main.py
  frontend/
    src/
      pages/
        ImplementationDashboardPage.tsx
        WarRoomSimulationPage.tsx
        ReportsPage.tsx
        PersonasPage.tsx
      components/
        ProposalBoard.tsx
        FrictionHeatmap.tsx
        PriorityMatrix.tsx
        KPITrendChart.tsx
        ConsensusTimeline.tsx
        PersonaBuilder.tsx
        ReportViewer.tsx
  docs/
    architecture.md
    simulation-spec.md
    reporting-spec.md
```

## 8) Initial API Contract (Draft)

- `POST /api/implementation/start`
- `POST /api/implementation/start-from-report`
- `GET /api/implementation/status/{id}`
- `GET /api/implementation/result/{id}`
- `POST /api/implementation/batch/start`
- `GET /api/implementation/batch/status/{batch_id}`
- `GET /api/implementation/batch/result/{batch_id}`
- `POST /api/personas/generate`
- `POST /api/graph/build`
- `POST /api/reports/generate`
- `GET /api/reports/status/{id}`
- `GET /api/reports/{id}`

## 9) Initial Data Model (Draft)

Suggested core tables:

- `companies`
- `departments`
- `stakeholders`
- `business_processes`
- `process_bottlenecks`
- `kpi_baselines`
- `ai_use_cases`
- `implementation_proposals`
- `implementation_rounds`
- `implementation_decisions`
- `simulation_results`
- `implementation_reports`
- `domain_events`

## 10) Output Report Template (Draft)

Required sections:

- Executive Summary
- Priority Matrix (value vs effort vs risk vs adoption)
- Department Friction Map
- KPI Impact Forecast (3/6/12 months)
- Simulated ROI by use case
- Risk Register and mitigations
- Governance and compliance checklist
- Recommended phased rollout roadmap
- “No-go” use cases and reasons

## 11) Strategic Persona JSON Example

```json
{
  "id": "persona_cfo_01",
  "role": "CFO",
  "display_name": "Skeptical CFO",
  "primary_goal": "Maximize ROI while minimizing budget and execution risk",
  "decision_power": "budget_owner",
  "technical_skill_level": "low_to_medium",
  "risk_tolerance": "low",
  "success_metrics": [
    "payback_period_months <= 18",
    "operating_margin_improvement >= 2%"
  ],
  "hard_constraints": [
    "no_unbounded_cloud_spend",
    "must_pass_security_and_legal_review"
  ],
  "trigger_conditions": {
    "challenge_if": [
      "simulated_roi_confidence < 0.65",
      "implementation_cost_growth > 25%"
    ],
    "support_if": [
      "pilot_kpi_improvement >= target",
      "change_management_plan_is_present"
    ]
  },
  "default_questions": [
    "What is the payback period?",
    "What are the downside scenarios?",
    "What budget guardrails are in place?"
  ]
}
```

## 12) Build Plan (MVP)

Phase 1:

- Implement business ontology extraction and graph schema.
- Implement 5 stakeholder persona templates.
- Build proposal-feedback loop with consensus scoring.

Phase 2:

- Add monthly timestep engine and KPI/adoption/cost models.
- Add batch scenario comparisons.
- Add report sections: priority matrix, friction map, simulated ROI.

Phase 3:

- Add governance policy checks, approval gates, and audit events.
- Add enterprise integration readiness scoring.
- Add model monitoring and rollback simulation.

## 13) Prompt You Can Paste Into Another AI

Use this prompt:

“I have an existing FastAPI + React multi-agent simulation app. Please help me implement a new domain: Business AI Implementation War Room.  
Use this architecture skeleton as source of truth.  
Generate:
1) A concrete 2-week implementation backlog with file-level tasks.
2) Initial backend code stubs for ontology extraction, persona templates, and implementation simulator.
3) Pydantic schemas and SQLAlchemy models for proposals, rounds, decisions, and KPI forecasts.
4) Frontend page/component stubs for Proposal Board, Priority Matrix, and Friction Heatmap.
5) A test plan covering unit, integration, and simulation consistency checks.”

