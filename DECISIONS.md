# Decisions Log

One entry per major decision: what we chose, what else we considered, why.

## D-001 Domain: sterile syringe fill line, filter integrity testing as the core
- **Chosen:** a fictional prefilled-syringe line with Tyvek removal, two filter integrity test carts per line,
  rotary filling and vacuum stoppering. Filter integrity is the main investigation area.
- **Considered:** automotive welding line (data already existed), filter integrity only.
- **Why:** filter integrity investigations need evidence from many systems (historian, MES, ERP, CMMS,
  autoclave, QMS), which is exactly what an agentic investigator is for. The other stations add cases where
  evidence is unrelated, so agents must tell related from unrelated.

## D-002 Synthetic data in two layers: truth, then messy export
- **Chosen:** simulate what physically happened first (`datagen/simulate.py`), then write what each source
  system would record, with its own flaws (`datagen/export.py`).
- **Considered:** writing messy CSVs directly.
- **Why:** every messy file can be checked against a known truth, and the answer key (`data/eval/`) is
  produced from the same run, so evaluation is exact.

## D-003 Planted scenarios overlap in time on purpose
- **Chosen:** e.g. cart seal wear (S1) overlaps a new filter lot (red herring) and a filler needle problem
  (S8); sensor drift (S5) overlaps the bad filter lot (S2) on line C.
- **Considered:** isolated, one-at-a-time scenarios.
- **Why:** real investigations are hard because several things change at once. Agents must rule causes out,
  not only find one that fits.

## D-004 Answer key isolated in `data/eval/`, enforced by a test
- **Chosen:** no scenario names or labels anywhere in `data/raw`; `tests/test_datagen.py` fails if they leak.
- **Why:** prevents accidentally training on, or prompting with, the answers.

## D-005 Acceptance tests prove each scenario is detectable from raw data
- **Chosen:** tests check, using raw files only, that each scenario leaves a statistically visible signal.
- **Why:** if a scenario is too weak to detect, the agents would be evaluated on an impossible task.

## D-006 Tech stack: AWS-native, production-style
- **Chosen:** Python 3.11; pandas + Parquet + DuckDB + Pandera for data; SciPy/statsmodels then
  scikit-learn for anomaly detection; **AWS Bedrock** (Claude models + embeddings) as the LLM; a plain
  Python agent loop first, then LangGraph; Pydantic for structured outputs; PostgreSQL + pgvector for app
  data, sessions and RAG; Redis for caching; FastAPI with streaming; Langfuse for tracing; pytest-based eval
  harness; Docker Compose locally; GitHub Actions CI; AWS (S3, ECS Fargate, RDS, ElastiCache, Secrets
  Manager, CloudWatch) provisioned with Terraform.
- **Considered:** direct Claude/OpenAI API (simpler setup), a separate vector database, Snowflake,
  LangSmith.
- **Why:** goal is maximum closeness to production. One cloud account for LLM, data and deployment;
  pgvector avoids an extra service at this scale; DuckDB is free and local; Langfuse is open source and
  self-hosted. Building the agent loop by hand first shows what LangGraph does underneath.

## D-007 Dataset v2: two years, delivered as daily drops
- **Chosen:** 730 days; each source system delivers a daily drop (`data/raw/drops/YYYY-MM-DD/<system>/`)
  with realistic behaviour: upserts (MES, CMMS, QMS), ERP reversals, late and resent historian rows, a
  3-day outage with backfill, a historian schema and tag-name change, and a CMMS column added mid-way.
- **Considered:** one static 120-day snapshot (v1).
- **Why:** v1 was too short for a 6-month training window and could not teach incremental loading,
  idempotency, schema evolution or point-in-time investigation, which are core production skills.

## D-008 Realistic statistics and text
- **Chosen:** log-normal flows with a right tail, slow cart aging reset by seal replacement, yearly room
  temperature cycle, crews and shifts, terse work order notes with abbreviations, incoming lot inspection,
  cart alarm log, and a recurrence of an earlier failure (S10 repeats S1 on another cart).
- **Why:** matches what real filter integrity data looks like (non-normal, drifting), and the recurrence
  lets the agent use memory of past closed investigations.

## D-009 Generated data is not committed
- **Chosen:** `data/raw/` and `data/eval/` are gitignored; anyone can regenerate them deterministically.
  Reference data, SOP docs and the data dictionary are committed.
- **Why:** about 200 MB of CSVs does not belong in git. In production the drops land in S3.

## D-010 Minimal CI before the first code PR, not in Phase 6
- **Chosen:** before Day 2 (landing + bronze), add a GitHub Actions workflow that runs `pytest` on every
  pull request, and branch protection on `main` so a PR cannot merge unless it passes. All changes reach
  `main` through a feature branch and a PR. Linting and the eval harness are added later. CD (automatic AWS
  deployment) stays in Phase 6.
- **Considered:** CI in Phase 6 with the rest of the deployment work (original plan).
- **Why:** the production standard "CI blocks merges on failure" cannot hold in Phases 2-5 without CI.
  Real teams add basic CI at the start; adding it late means months of code never checked automatically.
  CD waits because there is nothing to deploy until the API exists.

## D-011 Questionable "test complete" readings: keep the result and flag it
- **Chosen:** when the step-1300 ("test complete") reading of a test has quality `Questionable` but the
  flow and pressure at that moment are `Good`, the test result is kept and used, with a flag
  "step marker questionable" carried into silver and gold. More generally, Questionable rows are never
  deleted; the quality flag is carried through.
- **Considered:** A) use as normal and ignore the flag; C) quarantine the test until someone checks it.
- **Why:** 27 tests affected; for all of them the result (flow) and condition (pressure ~2500 mbar) are
  `Good`. Quarantining would block valid-looking results without a real reason; ignoring the flag would
  silently drop a data quality signal, which is not acceptable in GMP. The flag lets the agent and the
  reviewer see the doubt.

## D-012 Match assemblies to completed and cancelled batches; product impact only for completed
- **Chosen:** when matching filter assemblies to MES batches (gold), use batches with final status
  `COMPLETED` or `CANCELLED`. Exclude only test and placeholder records (`TEST` status, `B000000`,
  `B000001`, `NA-PENDING`). Carry the batch `status` onto the matched assembly. Product impact (units
  affected, release/reject) uses `COMPLETED` batches only.
- **Considered:** match only to batches where filling happened (`COMPLETED`).
- **Why:** all 13 cancelled batches have the comment "Batch cancelled - filter integrity failure on
  replacement assembly". These are exactly the deviations the agent must investigate; excluding them would
  cut the link between the failed assemblies and their batch. Cancelled batches have 0 tubs and 0 good
  units, so they have no product impact.
