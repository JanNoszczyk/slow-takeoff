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


---

## 6. Detailed task descriptions

Below you’ll find a plain-language explanation of what each task is meant to achieve, why it matters, and what you should expect to have in your hands once it’s finished. Think of these as mini-mission briefs rather than technical check-lists.

### T-01  Bootstrap repository & CI/CD
Imagine unpacking a brand-new laptop and being able to run the whole project with a single command. This task sets up that experience. We’ll arrange the folder structure, add Docker files so every service runs consistently, and wire in a GitHub Actions pipeline that automatically tests and deploys when we push to the main branch. When it’s complete, any team-mate—or judge—can clone the repo, type **`make dev`**, and watch the full stack come alive locally; a tagged release will appear online in Cloud Run without human intervention.

### T-02  Entity-resolution pipeline
Wealth Arc sometimes lists the same security multiple ways (different tickers, misspelled names). This job cleans that up. Each night it copies the raw asset list into BigQuery, asks Google’s Entity Resolution service to point out duplicates, and falls back to an open-source matcher if Google isn’t available. The outcome is a tidy table where every instrument has a single, permanent ID we can trust across all downstream analytics.

### T-03  Analytics service skeleton
All our agents need a common brain to query positions, valuations and basic portfolio math. This task builds that brain. We’ll spin up a FastAPI micro-service that talks to Postgres through SQLModel. It won’t perform fancy calculations yet, but it will already answer simple questions like “give me Yann Sommer’s current positions” and “what’s the year-to-date PnL?”. Future agents will rely on these endpoints instead of poking the database directly.

### T-04  Market-Pulse agent
Portfolios age quickly without live prices. Market-Pulse is a background worker that wakes up every few minutes, fetches fresh quotes and corporate-action notices, and drops them into our price table. Think of it as the project’s heartbeat: it keeps valuations current so later tasks—performance, risk, ESG—can reason against the latest market reality.

### T-05  Performance-Explainability agent
Numbers alone rarely satisfy clients; they want stories. This agent takes a portfolio’s recent performance and explains it in plain English—e.g., “70 percent of yesterday’s loss came from Tesla; currency moves added another 20 percent.” When finished, you’ll be able to hit one endpoint and receive a concise, human-readable paragraph you can paste straight into an email or slide.

### T-06  Factor-Risk agent
Here we translate the abstract idea of “risk” into concrete exposures—beta to equity markets, sensitivity to interest-rate shocks, and so on. The agent downloads standard factor datasets, runs regressions against our portfolios and produces a table of betas plus a what-if scenario (“if rates rise 1%, expect a 0.8% draw-down”). It arms the team with a quick-and-dirty risk report without firing up a heavy quant stack.

### T-07  Sentiment-Scout agent
Headlines move markets. Sentiment-Scout scours Google News, Reddit and other public sources for mentions of the assets we hold, gauges whether the chatter is positive or negative, and stores a rolling sentiment score. Portfolio managers can glance at a dashboard and instantly sense whether the crowd is cheering or booing their positions.

### T-08  ESG-Lens agent
Environmental, social and governance scores are indispensable for modern portfolios. ESG-Lens cross-references each resolved asset against external ESG datasets and attaches a risk rating. It also watches for sudden changes—say an oil spill that hurts a company’s score—and raises a flag so the team can react early.

### T-09  AML-Investigator agent
Anti-money-laundering checks often feel like endless paperwork. This agent builds a graph of clients, transactions and sanctioned entities, then applies simple rules (e.g., rapid round-tripping of cash) to surface anything dubious. The deliverable is a JSON alert and a Neo4j visual you can click through—perfect demo fodder for judges curious about compliance tech.

### T-10  LangGraph agent-swarm controller
Individually, our agents are useful; together, they’re magical. The controller describes a flow where Market-Pulse feeds fresh data to the analytics agents, which in turn hand their findings to a final summariser. It coordinates retries and time-outs so the whole conversation finishes in seconds. Once in place, you’ll be able to ask one natural-language question and receive a stitched-together answer drawing on every specialist.

### T-11  Story-Mode reporter
Rather than dumping raw JSON, this task assembles a polished daily report—charts, tables and narrative—exported as both PDF and PowerPoint. Imagine the CEO opening her inbox each morning to a brief that looks like it came from a Big-Four consultancy, except no analyst stayed up all night to craft it.

### T-12  Streamlit dashboard
For live demos, nothing beats a clickable dashboard. This task produces a Streamlit web app with three tabs: Overview KPIs, Risk metrics, and ESG insights. Data updates automatically via websockets, so the numbers dance on screen while you talk.

### T-13  Slack ChatOps Concierge
Many users live in Slack all day. The Concierge lets them type commands like `/wa pnl 30825 ytd` and receive an instant text-and-chart reply. It turns our platform into a friendly chat companion and avoids the need for everyone to bookmark yet another web URL.

### T-14  Observability stack
Stuff breaks—especially during live demos. By weaving OpenTelemetry and Prometheus metrics into every service, this task ensures we can see latency spikes, error rates and database bottlenecks in Grafana Cloud before the audience notices.

### T-15  Demo script & README polish
Finally, we’ll write a clear, step-by-step guide that spins up the whole system from scratch, seeds a bit of fake data and walks through a demo scenario. It’s the document that lets judges—and future developers—recreate the magic long after the hackathon lights go out.

---

Each of these missions produces something tangible you can open, run or read. Together they paint the full picture: a data-rich, agent-driven platform that feels alive and helpful from the first splash screen to the final PDF.