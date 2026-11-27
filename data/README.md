# Synthetic Data: Sterile Syringe Fill Line

Fictional, deterministic data for a sterile prefilled-syringe fill line. 3 lines, 120 days
(1 Jun – 29 Sep 2026), about 225 batches. **Nothing here comes from a real company or plant.**
Equipment IDs, vendors, products and spec limits are all made up.

Regenerate with `python -m datagen.generate` (seed 42, same output every time).

## The line

```
Tub (160 syringes, 10x16) → Tyvek removal robot → filter carts → rotary filler (10 needles) → vacuum stoppering

Per batch, each line uses two filter integrity test carts:
  cart 1 = formulation filtration, cart 2 = final-fill filtration
  build assembly → wet → Pre-IT → autoclave → PUPSIT → filtration during batch → post-use test
```

A failed test can be repeated (max 3 attempts). If all attempts fail, the assembly is rejected, a
deviation is opened and a replacement assembly is built. If the replacement also fails, the batch is cancelled.

## Folder layout

| Path | Source system | Grain |
|---|---|---|
| `raw/historian/assembly_summary/LINE-*_export_*.csv` | Historian export (Seeq-style) | One row per filter assembly |
| `raw/historian/test_signals/FITC_*_YYYY-MM.csv` | Historian time series | One row per 2 s during tests |
| `raw/mes/batches.csv` | MES | One row per batch |
| `raw/erp/material_consumption.csv` | ERP | One row per material lot used per batch |
| `raw/autoclave/cycles.csv` | Autoclave controller | One row per sterilization cycle |
| `raw/cmms/work_orders.csv` | CMMS (maintenance) | One row per work order |
| `raw/qms/deviations.csv` | QMS | One row per deviation |
| `raw/line/tyvek_removal_alarms.csv` | Line PLC alarm log | One row per alarm |
| `raw/line/filling_checks.csv` | Filler checkweigher | One row per needle per 30 min |
| `raw/line/stoppering_checks.csv` | Stoppering station | One row per station per 30 min |
| `raw/environment/room_conditions.csv` | Building management | One row per line per hour |
| `reference/equipment_master.csv` | Asset register | One row per equipment |
| `reference/spec_limits.yaml` | Specs | Limits |
| `docs/*.md` | SOPs and guides | For the knowledge (RAG) agent |
| `eval/` | **Answer key** | Offline evaluation only |

## Key columns

**Historian assembly summary:** `FIT_Cycle_Window` (assembly build start – PUPSIT end, UTC, as one string),
`Cart` (alias, varies), `PreIT_Flow`, `PUPSIT_Flow`, `PostUse_Flow` (mL/min, final attempt), `Wetting_Time`
(first wetting, text with " s"), `Attempts` (pre-IT attempts), `PUPSIT_Attempts`. **No batch ID**: assemblies
must be matched to batches by time.

**Test signals:** `StepIndex` (recipe step: 0 idle, 100 init, 200–400 pressurize, 500 stabilize, 600 checks,
1200 measure, 1300 test complete, 1400 release, 1500 cleanup, 9999 abort), `Pressure (mbar)`,
`Diffusion Flow (mL/min)`. Valid final flow = value at StepIndex 1300.

**MES batches:** `batch_id`, `line`, `product`, `recipe`, `batch_start`, `batch_end` (UTC), `status`,
`tubs_processed`, `total_good`, `rejects`.

**ERP material consumption:** `batch_id`, `material_code` (filter capsule, syringes, stoppers), `vendor_code`,
`vendor_lot`, `step_text`, `posting_date` (local date).

**Autoclave cycles:** `autoclave_id`, `cycle_start`, `cycle_end`, `max_chamber_temp_c`, `hold_time_min`,
`load_description` (free text). No batch or assembly ID: join by time and line.

**CMMS work orders:** `wonum`, `location` (CMMS location code, map via equipment master), `worktype`
(PM, PMCAL, CM, SA), `createdate`, `actfinish` (local time), `description`, `longdescription` (HTML).

## Deliberate data problems (handle them in ingestion)

| Problem | Where |
|---|---|
| Overlapping exports → duplicate rows, rows not in time order | Historian summary, test signals (month files overlap by 1 day) |
| Cart written 4 ways (`A1`, `FITC_A1`, `Cart A1`, `FITC-A1`) | Historian summary, deviations |
| `-` for missing values, `" s"` suffix on wetting time | Historian summary |
| Flow `0` = aborted test, not a measurement | Historian |
| Empty assembly rows (`Attempts` = 0) | Historian summary |
| Historian compression drops the StepIndex 500 rows in ~30% of tests | Test signals |
| Assembly-to-batch matching: ~82% start inside batch window, ~9% only end inside, ~9% in changeover gap | Historian vs MES |
| Dummy batch `B000000`, incomplete batch `NA-PENDING` | MES |
| Vendor lot blank in ~45% of filter rows (vendor code only) | ERP |
| Two `step_text` variants for the same step | ERP |
| Local time (IST, UTC+5:30), two date formats, truncated `statusdate`, HTML text | CMMS |
| Legacy location names (`FITC-0n`) in older work orders | CMMS |
| Unclear work type `SA` | CMMS |
| Line C temperature in °F, other lines °C; ~1% hours missing | Environment |
| Deviations appear 1–5 days after opening; recent ones not yet published | QMS |
| Initial deviation assessments are sometimes wrong | QMS |
| Different fill weight targets per product (1.0 mL vs 0.5 mL) | Filling |

## What happened (summary only)

Nine planted events plus one red herring: equipment wear, a bad supplier lot, a sterilization fault, sensor
drift, procedure errors, and benign changes. Some overlap in time on purpose. Full details, with windows and
confirmed causes, are in `eval/scenario_labels.json`.

## Rule

`eval/` is the answer key. **Never** load it into pipelines, features, prompts, retrieval or agent tools.
Use it only to score results.
