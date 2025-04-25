# WealthArc Agent Swarm  
*Hackathon 2025 – master plan & task board*

---

## 0. Elevator pitch
Turn the Wealth Arc data feed into **chef‑kiss actionable intelligence**:
* real‑time performance attribution
* risk & ESG lenses
* AML red‑flags
* gorgeous automated reports
* all driven by an orchestrated swarm of specialised agents.

Back‑fill is already covered by Wealth Arc, so we focus on **enrichment + narrative.**

---

## 1. Feature blocks
| Code | Feature block | Purpose | Demo‑wow ★ | Utility ★ |
|------|---------------|---------|-------------|-----------|
| **A** | **Entity hub** | Resolve instruments/clients into canonical IDs via BigQuery ER or Splink | ★★★ | ★★★★★ |
| **B** | **Analytics core** | Compute PnL, factor risk, ESG & compliance metrics | ★★★ | ★★★★★ |
| **C** | **Agent swarm** | Parallel specialised agents orchestrated with LangGraph/CrewAI | ★★★★★ | ★★★★ |
| **D** | **Output layer** | Streamlit dashboard, Slack bot, PDF reporter | ★★★★★ | ★★★★ |
| **E** | **Glue & ops** | Docker, CI/CD, observability | ★★ | ★★★★★ |

Legend – ★ out of 5.

---

## 2. Repository layout
```
/agent-swarm
├── apps/                # FastAPI, agent services, dashboard
│   ├── analytics/       # Feature block B
│   ├── agents/          # Feature block C
│   ├── api_gateway/     # existing WealthArc proxy
│   └── output_layer/    # dashboard, Slack bot, reporter
├── infra/               # Docker, Terraform, GitHub Actions
├── notebooks/           # quick explorations
└── docs/                # arch diagrams, this README
```

---

## 3. Master task board
*(Add ✅ when done, assign initials in **Owner**)*

| ID | Task (verb–noun) | Depends on | Diff. | Demo ★ | Util. ★ | Owner | Status |
|----|------------------|-----------|-------|--------|---------|-------|--------|
| **T‑01** | Bootstrap repo & CI/CD | — | S | ★★ | ★★★★★ | | ☐ |
| **T‑02** | Entity‑resolution pipeline (BQ ER + Splink fallback) | T‑01 | M | ★★★ | ★★★★★ | | ☐ |
| **T‑03** | Analytics service skeleton (FastAPI + SQLModel) | T‑01 | S | ★★ | ★★★★★ | | ☐ |
| **T‑04** | Market‑Pulse agent (live quotes & corp‑actions) | T‑03 | S | ★★★★ | ★★★★ | | ☐ |
| **T‑05** | Performance‑Explainability agent | T‑03,T‑04 | M | ★★★★ | ★★★★★ | | ☐ |
| **T‑06** | Factor‑Risk agent (Fama‑French & macro stress) | T‑04 | M | ★★★ | ★★★★ | | ☐ |
| **T‑07** | Sentiment‑Scout agent (news & social scrape) | T‑03 | M | ★★★★ | ★★★ | | ☐ |
| **T‑08** | ESG‑Lens agent (map to Sustainalytics/ISS) | T‑02 | M | ★★★ | ★★★★ | | ☐ |
| **T‑09** | AML‑Investigator agent (graph + sanctions) | T‑02,T‑07 | **L** | ★★★★ | ★★★★ | | ☐ |
| **T‑10** | LangGraph agent‑swarm controller | T‑04‑T‑08 | S | ★★★★ | ★★★ | | ☐ |
| **T‑11** | Story‑Mode reporter (PDF/PowerPoint) | T‑05‑T‑07 | S | ★★★★★ | ★★★ | | ☐ |
| **T‑12** | Streamlit dashboard | T‑04‑T‑08 | M | ★★★★★ | ★★★★ | | ☐ |
| **T‑13** | Slack “ChatOps Concierge” bot | T‑10 | S | ★★★★★ | ★★★ | | ☐ |
| **T‑14** | Observability stack (OpenTelemetry → Grafana) | T‑01 | S | ★★ | ★★★★ | | ☐ |
| **T‑15** | Demo script & README polish | all | S | ★★★★ | ★★★★ | | ☐ |

Diff. key – **S** ≤3 h, **M** 6–8 h, **L** >8 h.

---

## 4. Parallel sprint plan
- **Day 1 morning**  T‑01 (pair) → branch to T‑02 & T‑03 by lunch.
- **Day 1 afternoon**  T‑04, 06, 07, 14 fire in parallel.
- **Day 2 morning**  T‑08 + T‑10; T‑09 starts (long‑runner).
- **Day 2 afternoon**  T‑11, 12, 13; finish with T‑15.

---

## 5. Stretch goals (post‑demo)
- Browser‑Pilot agent that executes trades in custodian sandbox.
- Reinforcement‑learning evaluator to tune agent accuracy.
- Multi‑tenant auth & role‑based data scopes.

---

*Let’s ship something the judges have never seen.* 🚀

