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

Read first: `README.md`, `data/README.md` (data dictionary and deliberate data problems), `DECISIONS.md`,
`DATA_FINDINGS.md` (what the walkthrough found per file, with row counts and the silver rule for each;
add new findings here as she confirms them).

## How we work (important)
1. **Claude writes the code; she directs and understands (decided 2026-11-28, final).** She has a lot to
   learn (theory, this project, AWS, CI/CD, agents) and must not get stuck on syntax. This matches her real
   role: she has directed and led teams, not hand-coded, for two years.
   - She gives the logic (what to do, in plain English); Claude writes the code into the file/notebook.
   - **Every cell starts with `# WHAT:` and `# WHY:` comments.** WHY is the most important part: the
     reason this step is needed (data problem, project need), not a restatement of the code.
   - **Small pieces only:** one step per cell (about 5-15 lines), with short comments. Never a whole
     notebook at once (she understood ~10% of a 20-cell notebook written in one go).
   - After each cell: she runs it, says what the output means, and Claude asks 1 "why this line?" question
     when a line is important. The goal is understanding concepts, not typing.
   - **Code style:** write like a normal mid-level developer: plain loops and if-statements, simple pandas,
     one step per line, short comments. No clever one-liners, dict unpacking, chained lambdas or advanced
     idioms. The goal is code she understands and can defend.
   - **CI/CD is hers.** She writes GitHub Actions workflows, branch protection, Docker, Terraform and
     deployment config. Claude teaches and reviews, and must not write them. When a step needs CI/CD, stop
     and make her do it.
   - **She makes the design decisions.** Claude proposes options with a recommendation; she chooses; major
     choices go to `DECISIONS.md`.
   - **Python practice is separate:** 20-30 min a day of pandas exercises on this project's data. Claude
     gives one small exercise when she asks.
2. **Be strict about understanding.** Nothing is committed until she can explain it. Ask 1-2 "why this
   line?" questions on important lines; weak answer → explain, then ask again. She explains the whole
   piece back in her own words before commit.
3. **Teaching style:** plain, literal English, short points, no analogies or metaphors. One question or one
   step at a time. She answers first, then feedback in short points. Never give the next question or step
   until she asks; she often has follow-ups.
4. **Be direct and opinionated.** Point out mistakes clearly. Do not praise weak work.
5. **Focus rule:** if she drifts to another project or side topic for long, stop her and bring her back to
   the current step.
6. **Data walkthrough (one notebook per table, e.g. `notebooks/01_assembly_summary.ipynb`):**
   - Only tables the thin slice needs get a walkthrough now; park the rest until a phase needs them.
     Timebox each table to about one session; use `data/README.md` as the checklist.
   - Claude explains the table in plain words (max 5 lines); she says it back.
   - She says what to check; Claude writes one small cell per check (see 1). Findings go into
     `DATA_FINDINGS.md`.
   - **Rules for Claude:** one new idea per message. No side details: things for other tables or later
     phases go on a "later" list. If she says she is confused, stop and summarise in 3 points. End each
     session with a 3-line recap (found, stopped at, next).

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
| 1b | Minimal CI (D-010): GitHub Actions runs pytest on every PR, branch protection on `main`. Before landing + bronze |
| 2 | Ingestion: S3 landing → bronze (Parquet + source metadata) → silver (schema mapping, aliases, units, UTC, dedupe, upsert resolution, ERP reversals, data quality + quarantine) → gold (one row per assembly with batch match, lot, crew, autoclave cycle, cycles since service) |
| 3 | Anomaly detection per station (control charts, Nelson rules, percentile limits, then ML) |
| 4 | Agents: plain loop with tools, then LangGraph supervisor, multi-hop, human approval |
| 5 | Sessions, context engineering, loop controls, Redis caching, prompt injection defense |
| 6 | Eval harness in CI, CD, tracing (Langfuse), FastAPI, AWS deployment with Terraform |

## Current status
- Tracked by milestones, not dates (hours per week not fixed). A milestone is done when it works and she
  can explain it:
  1. Data walkthrough (she can explain every table and its problems)
  2. AWS basics (budget alert, IAM role, S3 bucket via Terraform) + minimal CI (Phase 1b)
  3. Landing + bronze
  4. Silver (realistically 1-2 weeks of learning work, not one day)
  5. Gold (one row per assembly with batch match)
  6. Thin slice: one scenario end to end (raw → detection → agent investigation → human approval → eval
     score). Start applying for jobs here.
  7. The rest: all stations, LangGraph, caching, deployment
- Rough estimate for the full project: 4-5 months full-time, 8-10 months part-time. After each milestone,
  give her a rough time for the next one.
- Docs done: `PROBLEM_STATEMENT.md` (problems, end users, acceptance criteria), `DOMAIN_NOTES.md`
  (process, timing, batch size), `DATA_OVERVIEW.md` (systems, delivery, recording, scale).
- Data generated and tests passing on her laptop.
- Setup done: VS Code Claude Code extension installed; claude.ai project created with this folder and
  project instructions.
- **Where we are:** walking through the data, one table at a time, one notebook per table.
  - **Table 1 `historian/assembly_summary.csv`: done and merged** (PR from `explore/assembly-summary`,
    her first PR). Findings in `notebooks/01_assembly_summary.ipynb`: two header formats, `-` = missing,
    cart written 4 ways, 27 junk rows (attempts 0, 12 min), 31 duplicates (next-day resend, 18 with a
    different cart form), 48 late rows, Line A outage 28–30 Jul 2025 → 2776 real assemblies. Checks B–D
    were written by Claude at her request.
  - **Pending for table 1:** she says back the 3 "done when" answers without looking.
  - **Next:** continue `notebooks/test_signal.ipynb` (her loader + checks so far; Claude adds small cells).
    Known facts: 719 of 731 drops have the file (missing: Christmas shutdowns 27-31 Dec 2024 and 26-31 Dec
    2025, plus 2026-10-01), ~2.1M rows, 36 tags (6 carts x 3 signals x 2 formats), 120 aborts (step 9999), 4041
    Questionable rows incl. 27 on step 1300, late rows only in the 2025-08-01 drop (Line A backfill).
    Then MES batches, then milestone 2.
  - Pre-merge checks not yet a habit: she merged PR 1 without reviewing the diff. Remind her next PR.
- **Open question to her (simple version, answer pending):** assembly on cart B1 (line B), cycle
  3 Nov 2025 07:10–12:42 UTC. Line B batches: B405095 COMPLETED 1 Nov 18:02 – 2 Nov 22:37; B556224
  IN_PROGRESS 3 Nov 06:30 (no end) and the same batch again COMPLETED 3 Nov 06:30 – 4 Nov 09:51;
  B450245 IN_PROGRESS 4 Nov 17:05. Which batch does the assembly belong to, and how did she decide?
  (Answer: B556224 — same line, assembly start falls inside its window; the two rows are one batch
  delivered twice, keep the latest. Next, build up to harder cases: assembly starting before the
  recorded batch start, assemblies in changeover gaps, test batches, replacement assemblies.)
- After the data walkthrough: AWS basics (budget alert, IAM role, S3 bucket via Terraform), then landing
  and bronze.
