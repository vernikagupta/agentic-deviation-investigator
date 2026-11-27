# CLAUDE.md — how to work in this repo

## Who and why
- Owner: Vernika, data scientist with 7 years experience (pharma manufacturing analytics), moving into Applied AI.
- This is her main portfolio project and her main learning track. The goal is **genuine learning** and a
  **production-grade** result she can defend line by line in interviews.
- Independent project. All data is synthetic and fictional. Never add real company, client, plant, equipment
  or people names, and never copy client code or data into this repo.

## The project
Agentic Deviation Investigator: detects and investigates deviations on a fictional sterile prefilled-syringe
fill line (Tyvek removal, two filter integrity test carts per line, rotary filling, vacuum stoppering).
Filter integrity testing (Pre-IT, autoclave, PUPSIT, post-use) is the core. Agents investigate anomalies
across historian, MES, ERP, QC, autoclave, CMMS, QMS, line and environment data, with human approval.

Read first: `README.md`, `data/README.md` (data dictionary and deliberate data problems), `DECISIONS.md`.

## How we work (important)
1. **She writes the code.** Claude explains, reviews and unblocks. Do not write core logic for her
   (ingestion rules, anomaly detection, agent loop, orchestration, caching, eval). Boilerplate, config,
   test scaffolding and data generation may be written by Claude when she asks.
2. **Teaching style:** plain, literal English, short points, no analogies or metaphors. One question or one
   step at a time. She answers first, then feedback in short points. Never give the next question or step
   until she asks; she often has follow-ups.
3. **Each step:** explain the goal and design choice → she codes → Claude reviews like a senior colleague
   (correctness, edge cases, production habits) → she explains it back → major choices go to `DECISIONS.md`
   → commit.
4. **Be direct and opinionated.** Point out mistakes clearly. Do not praise weak work.
5. **Focus rule:** if she drifts to another project or side topic for long, stop her and bring her back to
   the current step.

## Production standards
- No secrets in code or git. Config in files, not hardcoded. AWS via profiles/IAM roles, Secrets Manager.
- `data/eval/` is the answer key: never read it in pipelines, features, prompts, retrieval or agent tools.
- Pipelines never crash on bad rows: quarantine with a reason. Idempotent, incremental processing.
- Investigations use only data available at the investigation time ("as of").
- Tests for every module; CI blocks merges on failure.

## Stack (see DECISIONS.md D-006)
Python 3.11+, pandas, Parquet, DuckDB, Pandera, SciPy/statsmodels then scikit-learn, AWS Bedrock (Claude),
plain agent loop then LangGraph, Pydantic, PostgreSQL + pgvector, Redis, FastAPI, Langfuse, pytest,
Docker Compose, GitHub Actions, AWS (S3, ECS Fargate, RDS, ElastiCache, Secrets Manager, CloudWatch),
Terraform.

## Plan
| Phase | Content |
|---|---|
| 1 | Synthetic data (done: `datagen/`, 2 years of daily drops, 15 acceptance tests) |
| 2 | Ingestion: S3 landing → bronze (Parquet + source metadata) → silver (schema mapping, aliases, units, UTC, dedupe, upsert resolution, ERP reversals, data quality + quarantine) → gold (one row per assembly with batch match, lot, crew, autoclave cycle, cycles since service) |
| 3 | Anomaly detection per station (control charts, Nelson rules, percentile limits, then ML) |
| 4 | Agents: plain loop with tools, then LangGraph supervisor, multi-hop, human approval |
| 5 | Sessions, context engineering, loop controls, Redis caching, prompt injection defense |
| 6 | Eval harness in CI, tracing (Langfuse), FastAPI, AWS deployment with Terraform |

## Current status
- 3-day sprint (Nov 2026): Day 1 understand the data + AWS basics (budget alert, IAM role, S3 bucket via
  Terraform); Day 2 landing + bronze; Day 3 silver.
- Data generated and tests passing on her laptop.
- **Where we are:** walking through the data together. She found the number of files overwhelming, so go
  slowly: one table at a time, starting with one assembly row (historian summary) and the MES batches.
- **Open question to her:** an assembly cycle ran 21:11–02:32 UTC; the nearest batch on that line has
  batch_start 21:40. How would she match the assembly to a batch, and what could go wrong?
  (Expected direction: time-window matching in stages — start inside window, then end inside, then
  nearest — plus line constraint, upserts, changeover gaps, test batches, replacement assemblies.)
