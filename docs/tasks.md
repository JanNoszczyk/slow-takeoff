# WealthArc Agent Swarm  
*Hackathon 2025 – master plan & task board*

---

## 0. Elevator pitch
Turn the Wealth Arc data feed into **chef-kiss actionable intelligence**:

* real-time performance attribution  
* risk & ESG lenses  
* AML red-flags  
* gorgeous automated reports  

Back-fill is already covered by Wealth Arc, so we focus on **enrichment + narrative**.

---

## 1. Feature blocks

| Code | Feature block | Purpose | Demo-wow ★ | Utility ★ |
|------|---------------|---------|------------|-----------|
| **A** | **Entity hub** | Resolve instruments/clients into canonical IDs via BigQuery ER or Splink | ★★★ | ★★★★★ |
| **B** | **Analytics core** | Compute PnL, factor risk, ESG & compliance metrics | ★★★ | ★★★★★ |
| **C** | **Agent swarm** | Parallel specialised agents orchestrated with LangGraph/CrewAI | ★★★★★ | ★★★★ |
| **D** | **Output layer** | Streamlit dashboard, Slack bot, PDF reporter | ★★★★★ | ★★★★ |
| **E** | **Glue & ops** | Docker, CI/CD, observability | ★★ | ★★★★★ |

Legend – ★ out of 5.

---

## 2. Repository layout

/agent-swarm
├── apps/                # FastAPI, agent services, dashboard
│   ├── analytics/       # Feature block B
│   ├── agents/          # Feature block C
│   ├── api_gateway/     # existing WealthArc proxy
│   └── output_layer/    # dashboard, Slack bot, reporter
├── infra/               # Docker, Terraform, GitHub Actions
├── notebooks/           # quick explorations
└── docs/                # arch diagrams, this README

---

## 3. Master task board
*(Add ✅ when done, assign initials in **Owner**)*

| ID | Task (verb–noun) | Depends on | Diff. | Demo ★ | Util. ★ | Owner | Status |
|----|------------------|-----------|-------|--------|---------|-------|--------|
| **T-01** | Bootstrap repo & CI/CD | — | S | ★★ | ★★★★★ | | ☐ |
| **T-02** | Entity-resolution pipeline (BQ ER + Splink fallback) | T-01 | M | ★★★ | ★★★★★ | | ☐ |
| **T-03** | Analytics service skeleton (FastAPI + SQLModel) | T-01 | S | ★★ | ★★★★★ | | ☐ |
| **T-04** | Market-Pulse agent (live quotes & corp-actions) | T-03 | S | ★★★★ | ★★★★ | | ☐ |
| **T-05** | Performance-Explainability agent | T-03, T-04 | M | ★★★★ | ★★★★★ | | ☐ |
| **T-06** | Factor-Risk agent (Fama-French & macro stress) | T-04 | M | ★★★ | ★★★★ | | ☐ |
| **T-07** | Sentiment-Scout agent (news & social scrape) | T-03 | M | ★★★★ | ★★★ | | ☐ |
| **T-08** | ESG-Lens agent (map to Sustainalytics/ISS) | T-02 | M | ★★★ | ★★★★ | | ☐ |
| **T-09** | AML-Investigator agent (graph + sanctions) | T-02, T-07 | **L** | ★★★★ | ★★★★ | | ☐ |
| **T-10** | LangGraph agent-swarm controller | T-04–T-08 | S | ★★★★ | ★★★ | | ☐ |
| **T-11** | Story-Mode reporter (PDF/PowerPoint) | T-05–T-07 | S | ★★★★★ | ★★★ | | ☐ |
| **T-12** | Streamlit dashboard | T-04–T-08 | M | ★★★★★ | ★★★★ | | ☐ |
| **T-13** | Slack “ChatOps Concierge” bot | T-10 | S | ★★★★★ | ★★★ | | ☐ |
| **T-14** | Observability stack (OpenTelemetry → Grafana) | T-01 | S | ★★ | ★★★★ | | ☐ |
| **T-15** | Demo script & README polish | all | S | ★★★★ | ★★★★ | | ☐ |

Diff. key – **S** ≤ 3 h, **M** ≈ 6–8 h, **L** > 8 h.

---

## 4. Parallel sprint plan
* **Day 1 morning**  T-01 (pair) → branch to T-02 & T-03 by lunch.  
* **Day 1 afternoon**  T-04, T-06, T-07, T-14 fire in parallel.  
* **Day 2 morning**  T-08 + T-10; T-09 starts (long-runner).  
* **Day 2 afternoon**  T-11, T-12, T-13; finish with T-15.

---

## 5. Stretch goals (post-demo)

* **Browser-Pilot agent** – executes trades in custodian sandbox.  
* Reinforcement-learning evaluator to tune agent accuracy.  
* Multi-tenant auth & role-based data scopes.

---

## 6. Detailed task descriptions (copy-paste into your favourite coding-agent)

> Each task is self-contained: **context ▶︎ goal ▶︎ deliverables ▶︎ tech ▶︎ acceptance**.  
> _Environment variables_ reused across tasks: `WEALTHARC_API_KEY`, `POSTGRES_DSN`, `IEX_TOKEN`, `OPENAI_API_KEY`, `BQ_PROJECT`, `BQ_DATASET`.

### T-01 Bootstrap Repo & CI/CD
* **Context** Mono-repo scaffold that Dockerises every service and auto-deploys to Google Cloud Run on each main-branch push.  
* **Goal** Have a fresh dev spin-up in ≤1 command and an automated build-test-deploy pipeline.  
* **Deliverables**  
  1. `/docker-compose.yml` running `api_gateway`, `analytics`, `agents`, `db` (Postgres).  
  2. GitHub Actions workflow: lint → pytest → build multi-arch image → deploy to Cloud Run (use `$GCP_PROJECT` secret).  
  3. Makefile targets: `make dev`, `make test`, `make deploy`.  
* **Tech** Docker v25, GitHub Actions, Google Cloud SDK `gcloud run deploy`, `pip-tools` for lockfiles.  
* **Acceptance** Running `make dev` starts all containers; PR build shows green check; pushing a tag `v0.1.0` autoboots Cloud Run service reachable at `/ping`.

### T-02 Entity-Resolution Pipeline
* **Context** Wealth Arc gives assets with ISIN/VALOR but duplicates; we need a canonical `asset_id`.  
* **Goal** Nightly BigQuery ER job (primary) and a local Splink fallback that produces table `resolved_asset(id, isin, figi, name, source_ids[])`.  
* **Deliverables**  
  1. SQL DDL for `resolved_asset`.  
  2. Python script `jobs/resolve_assets.py` that:  
     * fetches `/myodata/Assets`, uploads to `BQ_DATASET.staging_assets`,  
     * calls BigQuery Entity Resolution API (config YAML in `/jobs/er_config.yaml`),  
     * stores results into Postgres.  
  3. Fallback path using `splink` with at least “name”, “isin” blocking rules.  
  4. GitHub Action schedule: `cron: '0 3 * * *'`.  
* **Tech** `google-cloud-bigquery[bqstorage]`, `google-cloud-entityresolution>=1.4`, `splink`, `sqlmodel`.  
* **Acceptance** After run, querying `resolved_asset` for sample ISIN returns exactly one row; unit test proves duplicates collapsed.

### T-03 Analytics Service Skeleton
* **Context** Agents call into a common micro-service for core metrics.  
* **Goal** FastAPI app exposing: `/positions`, `/pnl`, `/benchmark/{portfolio_id}` stub endpoints backed by SQLModel.  
* **Deliverables**  
  1. `apps/analytics/main.py` FastAPI.  
  2. SQLModel models mirroring Wealth Arc `Position`, `Portfolio`, plus computed `daily_pnl` table.  
  3. Alembic migration setup.  
* **Tech** `fastapi`, `sqlmodel`, `alembic`, `uvicorn[standard]`.  
* **Acceptance** `GET /pnl?portfolio_id=30825&period=ytd` returns JSON `{"total_pnl": …}` and unit tests hit 95 % coverage.

### T-04 Market-Pulse Agent
* **Context** Live prices & corporate-action awareness.  
* **Goal** Fetch intraday price for every `resolved_asset` every 5 minutes and store in `price_tick` table.  
* **Deliverables**  
  1. `agents/market_pulse/runner.py` async task using `yfinance` (free) and IEX Cloud (paid, optional).  
  2. Scheduler via `APScheduler` added to `apps/agents_scheduler`.  
  3. Alert webhook (just `print` in demo) when price gap > 10 % day-to-day.  
* **Tech** `asyncio`, `httpx`, `yfinance`, `apscheduler`.  
* **Acceptance** Tick table grows rows; integration test mocks yfinance and asserts DB insert.

### T-05 Performance-Explainability Agent
* **Context** Translate numbers into one-liner English insights.  
* **Goal** Endpoint `/explain/performance?portfolio_id=` returns dict `{headline, bullet_points[]}` covering attribution vs benchmark.  
* **Deliverables**  
  1. `generate_explanation(portfolio_id, period)` in `agents/performance_explain.py`.  
  2. Use `quantstats` for attribution and `openai` Chat Completion (`gpt-4o`) to draft prose.  
* **Tech** `quantstats`, `openai>=1.14`.  
* **Acceptance** Unit test snapshot-asserts that output text contains portfolio name and top driver (> 50 % attribution).

### T-06 Factor-Risk Agent
* **Context** Offer Fama-French & custom macro shock metrics.  
* **Goal** Route `/risk/factors` returning betas and shock scenario PnL.  
* **Deliverables** Fama-French data loader (download from Ken French website), OLS regression, shock simulation code.  
* **Acceptance** CI test injects synthetic returns and recovers known betas ± 0.05.

### T-07 Sentiment-Scout Agent
* **Goal** Scrape Google News + Reddit for each asset ticker; run OpenAI sentiment (-2…+2); persist `sentiment_score` table.  
* **Deliverables**  
  1. Playwright scraper w/ concurrency 5.  
  2. Simple exponential decay to compute 7-day rolling score.  
* **Acceptance** For known bullish news headline, sentiment ≤ -1.5 or ≥ 1.5 as expected.

### T-08 ESG-Lens Agent
* **Goal** Match assets to Sustainalytics CSV, return ESG risk score and flag changes > 5 pts.  
* **Acceptance** Integration test with sample ISIN maps correctly; change alert logged.

### T-09 AML-Investigator Agent
* **Context** Graph-based suspicious-flow detection.  
* **Goal** Neo4j graph with nodes (client, portfolio, transaction, asset, sanction_entity) and rule engine flagging layering, structuring.  
* **Deliverables**  
  1. Data loader → Neo4j via `py2neo`.  
  2. Rule: ≥ 3 transfers between same beneficiary within 24 h totalling > CHF 10k triggers alert doc.  
* **Acceptance** Synthetic fixture trips rule, alert JSON stored.

### T-10 LangGraph Agent-Swarm Controller
* **Goal** DAG: Market-Pulse → (Performance, Factor, Sentiment, ESG) ▶︎ join ▶︎ response.  
* **Acceptance** `python run_swarm.py "Why did Yann Sommer’s portfolio drop?"` prints combined analysis under 15 s.

### T-11 Story-Mode Reporter
* **Goal** Daily job builds `report_YYYY-MM-DD.pdf` & `.pptx` with charts and agent commentary.  
* **Acceptance** Runs with `PYTHONHASHSEED=0` yielding deterministic page count 8.

### T-12 Streamlit Dashboard
* **Goal** 3-tab UI: Overview (KPIs), Risk, ESG.  Live websocket push every 30 s.  
* **Acceptance** `streamlit run app.py` shows data without console error.

### T-13 Slack ChatOps Concierge
* **Goal** Slash command `/wa pnl 30825 ytd` replies with JSON card + chart image.  
* **Acceptance** Ngrok tunnel demo returns message < 2 s.

### T-14 Observability Stack
* **Goal** Prometheus metrics + OpenTelemetry traces for every FastAPI route.  
* **Acceptance** Visiting `/metrics` dumps Prom format; trace appears in Grafana Cloud.

### T-15 Demo Script & README Polish
* **Goal** MD script & shell file that reproduces end-to-end demo on fresh GCP project in ≤ 10 min.  
* **Acceptance** Mentor can copy-paste and reach dashboard URL.

---

> **Note:** Break any Medium/Large task into sub-issues as you go; cross-link back here so this top-level board stays tidy.

*Let’s ship something the judges have never seen.* 🚀