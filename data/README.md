# Synthetic Data: Sterile Syringe Fill Line (v2)

Fictional, deterministic data for a sterile prefilled-syringe fill line: 3 lines, **2 years**
(1 Oct 2024 – 30 Sep 2026), about 1,370 batches and 2,780 filter assemblies, delivered as **daily drops**
from each source system. **Nothing here comes from a real company or plant.**

```bash
python -m datagen.generate   # ~1 minute, same output every time (seed 42)
```

`data/raw/` and `data/eval/` are generated locally and not committed (about 200 MB). In production the
drops would land in object storage (S3), not in git.

## The line

```
Tub (160 syringes, 10x16) → Tyvek removal robot → filter carts → rotary filler (10 needles) → vacuum stoppering

Two filter integrity test carts per line: cart 1 = formulation filtration, cart 2 = final-fill filtration
Per batch and cart: build assembly → wet → Pre-IT → autoclave → re-wet → PUPSIT → filtration → post-use test
```

Failed tests are repeated (max 3 attempts). If all fail: deviation, replacement assembly; if that also
fails, the batch is cancelled. Crews rotate (4 per line, day/night). Carts age slowly between yearly seal
kit replacements.

## Layout

```
data/raw/drops/YYYY-MM-DD/
  manifest.json                       files and row counts in this drop
  historian/assembly_summary.csv      one row per filter assembly (Pre-IT, PUPSIT, both wetting times, attempts)
  historian/post_use_tests.csv        post-use test results (arrive after the batch)
  historian/test_signals.csv          long format: timestamp, tag, value, quality (stored on change)
  historian/cart_alarms.csv           cart alarm log
  mes/batches.csv                     batch records (upserts)
  erp/material_movements.csv          material postings incl. reversals
  qc/incoming_inspection.csv          filter lot incoming inspection
  autoclave/cycles.csv                sterilization cycles
  cmms/work_orders.csv                work orders (upserts)
  qms/deviations.csv                  deviations (upserts)
  line/tyvek_removal_alarms.csv       Tyvek removal robot alarms
  line/filling_checks.csv             fill weight per needle every 30 min
  line/stoppering_checks.csv          vacuum and plunger depth per station every 30 min
  environment/room_conditions.csv     room temperature and humidity per line, hourly
data/reference/                       equipment master (ID mapping across systems), spec limits
data/docs/                            fictional SOPs and troubleshooting guides (for RAG)
data/eval/                            ANSWER KEY - offline evaluation only
```

A drop contains only what that system delivered that day. A file is missing from a drop when the system
had nothing new.

## How each system behaves

| System | Behaviour you must handle |
|---|---|
| Historian summary | No batch ID (match to batches by time: ~85% start inside the batch window, ~8% only end inside, ~7% in the changeover gap). Cart written 4 ways. `-` for missing. Flow `0` = aborted test. Rows with `Attempts` 0. ~2% of rows arrive 1–3 days late, ~1% delivered twice. Line A silent for 3 days (outage, day 300), then backfilled. |
| **Schema change** (1 Oct 2025, historian upgrade) | Summary columns renamed (`Cart`→`Equipment`, `PreIT_Flow`→`PreIT_DiffFlow_mL_min`, one window string → `Cycle_Start_UTC` + `Cycle_End_UTC`, `Wetting_Time` "85 s" → `PreIT_Wetting_Time_s` 85, `PUPSIT_Wetting_Time` → `PUPSIT_Wetting_Time_s`). Note the old name `Wetting_Time` means pre-IT wetting only). Signal tags renamed (`FITC_A1.Pressure` → `PLT1.LA.FITC1.PRES_MBAR`). Map via `reference/equipment_master.csv`. |
| Historian signals | Long format, values stored only when they change (irregular timestamps). StepIndex: 0 idle, 100 init, 200–400 pressurize, 500 stabilize, 600 checks, 1200 measure, **1300 test complete (valid final flow)**, 1400 release, 1500 cleanup, 9999 abort. A few values with quality `Questionable`. |
| MES | Each batch arrives twice: `IN_PROGRESS` at start, final record (`COMPLETED`/`CANCELLED`, totals, comment) at end. Keep the latest by `record_updated_at`. Test batches `B000000`, `B000001`; incomplete `NA-PENDING`. |
| ERP | Posted the day after use (local date). Movement `261` = issue, `262` = reversal (quantity −1). ~3% of filter postings use a wrong lot, then a reversal and a correct re-post a day or two later. Vendor lot blank in ~45% of filter rows. Two `step_text` variants. |
| QC incoming | One row per filter lot at receipt. Lots can pass incoming inspection and still be defective. |
| CMMS | Each work order arrives twice: `WAPPR` at creation (no finish, no notes), `COMP` at completion (with HTML notes). Local time (IST, UTC+5:30), two date formats, some truncated `statusdate`. Legacy location names (`FITC-0n`) before day 300. Work type `SA` is unclear. Notes are terse, with abbreviations and typos. `failurecode` column exists only from Feb 2026. |
| QMS | Deviations arrive 1–5 days after opening (`Open`, with an initial assessment that can be wrong), then again when closed (`Closed`, with root cause). Investigations must only use what was available at the time. |
| Environment | Line C in °F, others in °C. ~1% of hours missing. |
| Filling | Fill weight target depends on the product (1.0 mL vs 0.5 mL). ~0.5% blank weights. |

## Statistics

Flows are log-normal with a right tail (not normally distributed). Carts differ slightly from each other.
Pre-IT and PUPSIT are only weakly correlated. Flows creep up as carts age and reset after seal replacement.
Room temperature has a mild yearly cycle.

## What happened

Ten planted events plus one red herring over two years: equipment wear (twice on carts, the second a
recurrence of the first), a bad supplier lot, a sterilization fault, sensor drift, a crew procedure issue,
station problems, and a benign room temperature change. Several overlap in time on purpose. Details, windows,
confirmed causes and a suggested "investigate as of" time per event are in `eval/scenario_labels.json`.

## Rule

`eval/` is the answer key. **Never** load it into pipelines, features, prompts, retrieval or agent tools.
Use it only to score results.
