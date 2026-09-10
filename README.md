# WaterTwin AI

## Evidence-Based Intelligence for Water Infrastructure

**Detect. Investigate. Explain. Simulate. Prioritize. Act.**

> An AI decision engine that turns abnormal water usage data into evidence-backed actions to reduce water loss, cost and infrastructure inefficiency.

---

## 🌍 Why Water Intelligence Matters

Water infrastructure teams often receive alerts when consumption, flow or pressure behaves unexpectedly.

But an alert is not a decision.

The real operational questions are:

- What happened?
- Why did it happen?
- What evidence supports the explanation?
- How confident are we?
- What should be done?
- What impact could the action create?
- When should the system abstain?

WaterTwin AI is designed to close this decision gap.

### From

**Abnormal water usage → isolated alerts → manual investigation → uncertain action**

### To

**Abnormal usage → evidence → explanation → simulation → decision → impact**

---

## 💡 The WaterTwin Intelligence Loop

```text
DETECT
   ↓
INVESTIGATE
   ↓
EXPLAIN
   ↓
SIMULATE
   ↓
PRIORITIZE
   ↓
ACT
```

WaterTwin combines deterministic analytics with Gemini-powered investigation to move from anomaly detection to evidence-backed action.

The system is designed around one central question:

> **Do we have enough evidence to act?**

---

# ⭐ What Makes WaterTwin Different?

## Evidence + Confidence + Abstention

WaterTwin does not treat every anomaly as a reason to recommend an intervention.

Instead, it separates different types of information:

- **Observed evidence** — measurements directly available from the data
- **Calculated evidence** — deterministic metrics derived from the data
- **Contextual signals** — occupancy and weather
- **Infrastructure signals** — flow, pressure and meter quality
- **Hypotheses** — possible explanations for an anomaly
- **Missing information** — evidence required to resolve uncertainty

This enables four meaningful decision outcomes:

| Decision | Meaning |
|---|---|
| **RECOMMEND** | Evidence supports an actionable intervention |
| **EXPLAIN** | The evidence supports an explanation, but not enough certainty for action |
| **NO_ACTION** | No meaningful abnormality or intervention need is established |
| **ABSTAIN** | Evidence is weak, conflicting or insufficient; additional information is required |

If evidence is weak, conflicting or insufficient, WaterTwin can **ABSTAIN** rather than force a recommendation.

This makes uncertainty a first-class decision outcome rather than an error condition.

---

# 🤖 Multi-Agent Intelligence

WaterTwin uses specialized agents with distinct responsibilities.

The agents do not duplicate each other. Each contributes a different evidence stream or decision capability.

## 1. Consumption Agent

Analyzes:

- Water consumption history
- Baselines
- Deviations from expected consumption
- Significant anomalies
- Night-time consumption behavior

**Responsibility:** Determine what changed in consumption.

---

## 2. Context Agent

Analyzes:

- Occupancy
- Weather
- Temperature
- Contextual deviations

**Responsibility:** Determine whether external demand drivers can explain the consumption change.

---

## 3. Infrastructure Agent

Analyzes:

- Flow
- Pressure
- Meter status
- Reading quality
- Night-flow behavior

**Responsibility:** Determine whether infrastructure signals support a physical or measurement-related explanation.

---

## 4. Evidence Agent

Combines the outputs of the evidence-producing agents.

It identifies:

- Supporting evidence
- Conflicting evidence
- Evidence gaps
- Missing information
- Evidence strength

**Responsibility:** Build an evidence picture before the system makes a decision.

---

## 5. Gemini Investigation Engine

Gemini performs meaningful reasoning over the structured evidence.

It:

- Compares competing hypotheses
- Synthesizes evidence
- Explains the most supported interpretation
- Identifies uncertainty
- Distinguishes evidence from assumptions
- Produces structured machine-readable output

Gemini does **not** invent measurements, costs, savings or other numerical evidence.

---

## 6. Intervention Agent

Generates candidate actions aligned with the investigation.

Examples include:

- Leak inspection
- Pressure diagnostic
- Meter/data-quality check
- Demand management
- Weather-related demand control

Each candidate contains deterministic operational information such as:

- Estimated cost
- Expected impact
- Operational effort
- Feasibility

---

## 7. Recommendation Engine

The Recommendation Engine applies deterministic decision rules to the investigation and intervention outputs.

It considers:

- Investigation decision
- Root-cause hypothesis
- Evidence alignment
- Available intervention candidates
- Budget constraints
- Safety/abstention gates

It does not override an authoritative **ABSTAIN**, **EXPLAIN** or **NO_ACTION** decision simply because an intervention is available.

---

## 8. Intervention Simulator

The simulator is a major WaterTwin decision feature.

It evaluates whether an intervention is feasible under constraints such as:

- Budget
- Estimated intervention cost
- Expected water savings
- Operational impact

The simulator is deterministic.

This allows an evaluator or operator to change the available budget and observe how the feasible action changes without changing the underlying evidence.

---

## 9. ADK Orchestrator

The Google ADK Orchestrator coordinates the end-to-end workflow.

It connects:

```text
Consumption
     +
Context
     +
Infrastructure
     ↓
Evidence
     ↓
Gemini Investigation
     ↓
Intervention
     ↓
Recommendation
     ↓
Simulation
     ↓
Final Decision
```

---

# 🧪 Controlled MVP

WaterTwin is intentionally scoped to one controlled campus/water-zone scenario using synthetic data with known ground truth.

The MVP contains seven controlled scenarios:

| Scenario | Ground Truth | Expected Decision |
|---|---|---|
| **S1** | Normal consumption | NO_ACTION |
| **S2** | Continuous flow / leak | RECOMMEND |
| **S3** | Pressure anomaly | RECOMMEND |
| **S4** | Occupancy change | EXPLAIN |
| **S5** | Weather-driven demand change | EXPLAIN |
| **S6** | Sensor anomaly | ABSTAIN |
| **S7** | Conflicting evidence | ABSTAIN |

This controlled design makes it possible to evaluate not only whether the system detects anomalies, but whether it makes the **right type of decision**.

---

# 🔎 Scenario Examples

## S2 — Continuous Flow / Leak

WaterTwin detects a strong consumption deviation together with supporting flow and night-flow evidence.

The investigation identifies:

**Primary hypothesis: LEAK**

The intervention agent proposes:

**Leak inspection**

Deterministic intervention cost:

**₹4,000**

Expected water savings from the controlled scenario:

**4,210.21 L/day**

With a **₹20,000** budget:

```text
Intervention cost     ₹4,000
Budget                ₹20,000
Remaining budget      ₹16,000
Simulation status     ACTION_FEASIBLE
Decision               RECOMMEND
Confidence             HIGH
```

The key point is that the recommendation is not based on the anomaly alone.

It is supported by multiple evidence streams and then checked against operational constraints.

---

# 💰 Budget-Constrained Decision

The same leak scenario can be evaluated with a lower budget.

For example:

```text
Available budget      ₹3,000
Required intervention ₹4,000
```

WaterTwin produces:

```text
Decision               NO_ACTION
Reason                 BUDGET_CONSTRAINED
Primary hypothesis     LEAK
Simulation status      BUDGET_CONSTRAINED
```

The evidence does not change.

The intervention feasibility changes.

This demonstrates that the simulator is part of the decision process rather than a static display.

---

# 🛑 Abstention Is a Feature

## S6 — Sensor Anomaly

The system detects extreme consumption readings, but infrastructure evidence shows:

- Poor-quality meter readings
- Non-OK/degraded meter status
- No corresponding flow anomaly
- No corresponding pressure anomaly

The system therefore does not recommend a physical intervention.

```text
Decision           ABSTAIN
Root cause         SENSOR_ANOMALY
Confidence         LOW
```

WaterTwin requests additional information such as hardware diagnostics or field calibration rather than pretending the abnormal readings represent confirmed water loss.

---

## S7 — Conflicting Evidence

S7 contains meaningful contextual demand signals but also a separate pressure anomaly.

The evidence does not establish that occupancy or weather caused the pressure degradation.

WaterTwin therefore produces:

```text
Decision           ABSTAIN
Root cause         AMBIGUOUS
Confidence         LOW
```

The system identifies the missing evidence required to resolve the ambiguity, such as additional hydraulic information.

This is a core demonstration of the WaterTwin philosophy:

> **A trustworthy decision engine must know when not to act.**

---

# 🏗️ Evidence-Driven Architecture

```text
                  Synthetic Water Data
                         │
                         ▼
                    Google BigQuery
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        Consumption   Context   Infrastructure
           Agent       Agent        Agent
              └──────────┼──────────┘
                         ▼
                    Evidence Agent
                         │
                         ▼
              Gemini Investigation Engine
                         │
                         ▼
                 Intervention Agent
                         │
                         ▼
               Recommendation Engine
                         │
                         ▼
              Intervention Simulator
                         │
                         ▼
                 Final Decision
                         │
                         ▼
                    WaterTwin UI
```

Event-driven simulation is supported through Pub/Sub, while the application backend is deployed through Cloud Run.

---

# ☁️ Google Cloud Architecture

WaterTwin uses Google Cloud and Google AI technologies throughout the MVP.

## Core Google Cloud Services

| Service | Purpose |
|---|---|
| **BigQuery** | Synthetic water data, ground truth and deterministic analytics |
| **Pub/Sub** | Event-driven water anomaly simulation |
| **Cloud Run** | Backend/API deployment |
| **Artifact Registry** | Container image storage |
| **Secret Manager** | Secret/configuration management |
| **Firebase Hosting** | React frontend hosting |
| **Gemini API** | Evidence investigation and reasoning |
| **Google ADK** | Multi-agent orchestration |
| **Google AI Studio** | Gemini experimentation and development |
| **Antigravity IDE** | AI-assisted development |

---

# 🧮 Deterministic Analytics + Gemini Reasoning

WaterTwin intentionally separates deterministic computation from generative reasoning.

## Deterministic code / SQL handles

- Baselines
- Consumption deviations
- Anomaly thresholds
- Percentages
- Flow and pressure calculations
- Night-flow analysis
- Costs
- Expected savings
- Budget calculations
- Feasibility
- Ranking logic
- Evaluation metrics

## Gemini handles

- Comparing competing hypotheses
- Evidence synthesis
- Root-cause explanation
- Uncertainty identification
- Structured investigation reasoning

This separation prevents the LLM from becoming the source of truth for numerical measurements.

---

# 📊 Evaluation

The MVP uses controlled synthetic scenarios with known ground truth.

Evaluation focuses on:

- Anomaly detection accuracy
- False-positive rate
- Root-cause accuracy
- Correct decision semantics
- Confidence behavior
- Abstention behavior
- Intervention recommendation quality
- Estimated water saved
- Estimated cost savings

The repository includes:

`evaluation_full_7_scenarios.json`

This contains the full seven-scenario evaluation results used during validation.

---

# 📈 Success Metrics

WaterTwin should ultimately be evaluated on whether it can answer:

### Detection

Can it identify meaningful abnormal usage?

### Investigation

Can it distinguish among competing explanations?

### Evidence

Can it show why a hypothesis is supported or contradicted?

### Decision

Can it choose RECOMMEND, EXPLAIN, NO_ACTION or ABSTAIN appropriately?

### Confidence

Does confidence reflect the strength and quality of evidence?

### Action

Does the recommended intervention align with the identified problem?

### Impact

Can the simulator estimate the operational and financial impact of an action?

### Safety

Does the system abstain when evidence is insufficient?

---

# 🌊 Why WaterTwin Is More Than a Water Anomaly Detector

A conventional anomaly detector might produce:

```text
⚠ Abnormal consumption detected
```

WaterTwin attempts to produce:

```text
What happened?
       ↓
Why might it have happened?
       ↓
What evidence supports that explanation?
       ↓
What evidence conflicts with it?
       ↓
What information is missing?
       ↓
Is there enough evidence to act?
       ↓
What intervention is feasible?
       ↓
What impact could it create?
```

That is the difference between **detecting an anomaly** and **supporting a decision**.

---

# 🌍 Why This Problem Matters

Water efficiency is increasingly important as communities and infrastructure operators deal with:

- Water scarcity
- Climate variability
- Increasing demand
- Aging infrastructure
- Leakage and non-revenue water
- Operational inefficiency
- Data-quality problems
- Complex infrastructure decisions

Water intelligence can help shift water management from reactive alert handling toward evidence-based operational decision-making.

WaterTwin is intentionally not positioned as a replacement for field engineers, hydraulic experts or utility operators.

Instead, it is a decision-support layer that helps organize evidence, investigate anomalies and prioritize actions.

---

# 🚀 Impact Vision

The MVP demonstrates the decision pattern on a controlled campus/water-zone environment.

The longer-term vision is to extend the same evidence-driven architecture to larger water systems.

Potential future applications include:

- Campus water networks
- Industrial facilities
- Commercial buildings
- Residential communities
- District water zones
- Utility operations

The system could eventually integrate richer operational data such as:

- More detailed meter telemetry
- Pump information
- Pressure-reducing valve data
- Maintenance history
- Work orders
- Irrigation schedules
- Cooling-system schedules
- Additional hydraulic information

These are future extensions, not part of the current MVP.

---

# 🧭 Future Scalability

The architecture is designed so additional evidence sources can be introduced without changing the core decision philosophy.

For example:

```text
More Data
   ↓
More Evidence
   ↓
Better Hypothesis Comparison
   ↓
Better Confidence Calibration
   ↓
Better Decisions
```

The most important scalability principle is not adding more agents.

It is adding **better evidence**.

---

# 🛡️ Responsible AI and Governance

WaterTwin follows several principles:

### Evidence before action

Recommendations must be supported by available evidence.

### Deterministic numbers

Measurements, calculations, costs and savings are generated through deterministic analytics.

### Explainability

The system shows supporting evidence, conflicting evidence and missing information.

### Abstention

The system can refuse to recommend an intervention when evidence is insufficient.

### Human decision support

WaterTwin is a decision-support system, not an autonomous replacement for operational experts.

### Controlled evaluation

Known synthetic ground truth allows the system to be tested before applying the approach to real-world data.

---

# 🧪 Why Synthetic Data?

The MVP intentionally uses synthetic data.

This provides:

- Known ground truth
- Reproducible scenarios
- Controlled anomalies
- Safe experimentation
- No exposure of sensitive infrastructure data
- Direct evaluation of root-cause and abstention behavior

The goal is not to claim production utility accuracy from synthetic data.

The goal is to demonstrate and evaluate the **decision architecture**.

---

# 🔐 Security

The public repository is designed to contain source code and evaluation artifacts, not credentials.

Sensitive configuration should be supplied through environment variables or Google Cloud secret/configuration mechanisms.

No API keys, passwords or service-account credentials should be committed to the repository.

---

# 🎬 Final Demo Story

The strongest WaterTwin demonstration follows this sequence:

```text
Abnormal Usage
      ↓
Evidence Collection
      ↓
Multi-Agent Investigation
      ↓
Competing Root Causes
      ↓
Gemini Evidence Synthesis
      ↓
Confidence
      ↓
Intervention Simulation
      ↓
Prioritized Action
      OR
Abstention
```

The demo should show both sides of intelligent decision-making:

### When evidence is strong

**Detect → Investigate → Explain → Simulate → Prioritize → Act**

### When evidence is weak or conflicting

**Detect → Investigate → Explain → Abstain**

That contrast is central to the WaterTwin value proposition.

---

# ⭐ Core Differentiator

WaterTwin is built around three principles:

## 1. Evidence

Every meaningful decision should be traceable to observed and calculated evidence.

## 2. Confidence

Confidence should reflect evidence strength, agreement, conflict and data quality rather than being an arbitrary model-generated number.

## 3. Abstention

When the evidence is insufficient, the correct action can be:

> **Do not act yet. Collect more evidence.**

---

# 📦 MVP Scope

The current MVP intentionally focuses on:

- One controlled campus/water-zone scenario
- Synthetic water data
- Seven known-ground-truth scenarios
- BigQuery analytics
- Deterministic anomaly detection
- Gemini investigation
- Google ADK multi-agent orchestration
- Intervention recommendations
- Deterministic intervention simulation
- Confidence and abstention
- Pub/Sub event simulation
- Cloud Run backend
- React frontend
- Firebase Hosting

The MVP does **not** attempt to implement:

- Physical IoT deployment
- Full hydraulic simulation
- Municipal integrations
- Production utility infrastructure
- Autonomous field operations

This keeps the project focused, testable and demonstrable.

---

# 🌐 Deployed Application

**WaterTwin AI is deployed and accessible here:**

https://project-4e41dc93-8aec-4f29-8fd.web.app

The deployed application allows users to:

1. Select a controlled scenario
2. Select an intervention budget
3. Run the WaterTwin investigation
4. Review evidence
5. Compare hypotheses
6. View confidence
7. Review recommendations or abstention
8. Simulate intervention feasibility and impact

---

# 📁 Repository Structure

```text
watertwin-ai/
│
├── adk_orchestrator.py
├── consumption_agent.py
├── context_agent.py
├── infrastructure_agent.py
├── evidence_agent.py
├── investigation_engine.py
├── intervention_agent.py
├── intervention_simulator.py
├── recommendation_engine.py
├── evaluation_engine.py
├── pubsub_processor.py
├── water_twin_publisher.py
├── main.py
│
├── evaluation_full_7_scenarios.json
│
├── Dockerfile
├── requirements.txt
├── .dockerignore
├── .gitignore
├── README.md
│
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── App.css
    │   ├── index.css
    │   └── main.jsx
    ├── public/
    ├── package.json
    ├── package-lock.json
    ├── firebase.json
    └── vite.config.js
```

---

# 🔄 End-to-End Workflow

```text
1. DETECT
   Deterministic analytics identify abnormal usage.

2. INVESTIGATE
   Specialized agents collect consumption, context and infrastructure evidence.

3. EXPLAIN
   Evidence Agent and Gemini compare possible explanations.

4. SIMULATE
   Intervention candidates are evaluated against budget and operational constraints.

5. PRIORITIZE
   Recommendation logic selects an evidence-aligned feasible action.

6. ACT
   The system recommends an action or explicitly abstains.
```

---

# 🏆 Final Vision

WaterTwin AI aims to demonstrate a simple but important shift:

> **From AI that only detects problems to AI that helps decide what to do about them — and knows when it should not decide yet.**

The project brings together:

- Google Cloud
- BigQuery
- Gemini
- Google ADK
- Pub/Sub
- Cloud Run
- Firebase
- React
- Python
- Deterministic analytics
- Multi-agent reasoning
- Evidence-based decision-making
- Intervention simulation

The goal is not to make the system look artificially complex.

The goal is to make every component useful.

---

# Google Patchamomma 2026

**WaterTwin AI — Evidence-Based Intelligence for Water Infrastructure**

**Detect. Investigate. Explain. Simulate. Prioritize. Act.**

Built for the **Google Patchamomma 2026 Build Phase**.
