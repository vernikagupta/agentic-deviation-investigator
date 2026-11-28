# Data Findings

What the data walkthrough found, per file. Each finding becomes a silver-layer rule or test later.
Counts are over all drops (1 Oct 2024 – 30 Sep 2026). Notebook links show the evidence.

---

## historian/assembly_summary.csv
Notebook: `notebooks/01_assembly_summary.ipynb`

**One row:** one filter assembly's integrity tests (Pre-IT and PUPSIT). No batch ID.
**Rows:** 2834 in files → **2776 real assemblies** (after removing 27 junk rows and 31 duplicate copies).

| # | Finding | Rows | Silver rule |
|---|---|---|---|
| 1 | Two header formats; schema change on 1 Oct 2025 | 1403 old, 1431 new | map old and new column names to one name each |
| 2 | README misses two renames: `Attempts` → `PreIT_Attempts`, `PUPSIT_Flow` → `PUPSIT_DiffFlow_mL_min` | – | include in the column mapping |
| 3 | Old `Wetting_Time` and `Attempts` mean Pre-IT only (name does not say so) | – | rename to `preit_*` |
| 4 | Old cycle time is one string `"start - end"`; new has two columns | 1403 | split, convert to UTC datetime |
| 5 | Old wetting time is text with unit (`"85 s"`); new is a number | 1403 | strip unit, convert to number |
| 6 | Missing written as `-` (old); `isna()` does not count it | 45 in `PreIT_Flow` | read `-` as NaN (`na_values=["-"]`) |
| 7 | Pre-IT flow `-` but attempts ≥ 1: test ran, value not recorded | 28 | keep row, flow = NaN, flag "not recorded" |
| 8 | Junk rows: attempts 0, exactly 12 min long, all results `-` / blank (real rows 4.9–6.7 h) | 27 (17 old, 10 new) | quarantine, reason "empty assembly row" |
| 9 | Cart name written 4 ways (`A1`, `FITC_A1`, `FITC-A1`, `Cart A1`) in both `Cart` and `Equipment` | all | map to one `equipment_id` via `reference/equipment_master.csv` |
| 10 | Duplicates: same assembly resent in next day's drop; only 13 exact copies, 18 differ in cart form | 31 copies (~1.1%) | dedupe on start time + normalised cart, **after** rule 9 |
| 11 | Late rows: arrive 1–3 days after the test ended | 48 of 2776 (~1.7%) | incremental load must accept past dates |
| 12 | Line A outage 28–30 Jul 2025, backfilled in 1 Aug drop | 3 drops | covered by rule 11; compare lines to detect outages |
| 13 | Flow `0` (README: aborted test) does not appear in this file | 0 | none (aborts are visible in `test_signals.csv`) |

---

## historian/test_signals.csv
Notebook: `notebooks/test_signal.ipynb` (done)

**One row:** one sensor reading: timestamp, tag (cart + signal), value, quality. Long format, stored on change.
**Rows:** 2,125,464 from 719 drops.

| # | Finding | Rows | Silver rule |
|---|---|---|---|
| 1 | File missing in 12 drops: 27–31 Dec 2024, 26–31 Dec 2025 (Christmas shutdowns), 2026-10-01 (after data end). Some of these drops have no `historian` folder at all | 12 drops | loader must skip missing folders/files without crashing |
| 2 | No missing values in any column | 0 | – |
| 3 | 36 distinct tags = 6 carts × 3 signals × 2 formats (old `FITC_A1.DiffFlow`, new `PLT1.LA.FITC1.FLOW_MLMIN`) | all | split tag into cart + signal; map both formats to one name |
| 4 | No duplicates on the key (timestamp + tag) | 0 | still enforce the key in silver (unlike assembly summary) |
| 5 | Quality `Questionable` on 4,041 rows (0.19%). Even spread: same rate on flow, pressure and step (~0.19–0.20%), on all 6 carts (624–721 each), and on all steps → looks like random sensor/communication noise, not an equipment problem. The data does not say why a reading is Questionable (in a real plant: ask the automation team) | 4,041 | keep the rows and carry the quality flag through; never delete them silently |
| 5a | 27 Questionable readings are on step **1300 (test complete)**. For all 27, the flow (result) and pressure (~2500 mbar) at the same second are `Good` → the result looks trustworthy, only the completion marker is in doubt | 27 tests | keep the result and flag it "step marker questionable" (decision D-011) |
| 6 | Value `0.0` on 115,592 rows: step 0 (idle) 26,244, flow 52,368, pressure 36,980. Flow is 0 only in idle/init (0, 100), release/cleanup (1400, 1500) and abort (9999); pressure is 0 only in idle/init/start of pressurizing (0, 100, 200) and cleanup (1500). **Never 0 during stabilize → measure → complete (500–1300).** Physical reason: no test pressure → no gas flows through the filter, so flow 0 is a real reading, not missing | 115,592 | keep as real values; flag flow 0 or pressure 0 during steps 500–1300 as an anomaly (none today) |
| 7 | Mapping: all 36 tags map to one cart ID (`equipment_master.csv`) and one signal name (flow, pressure, step); 0 unmapped | 0 unmapped | map via equipment master; quarantine unknown prefixes ("unknown tag prefix") |
| 8 | Completed tests (step 1300) per cart: 1,404–1,462, within ~4% → carts used evenly. Row counts are not a fair usage measure (stored on change) | 8,628 tests | – |
| 9 | Test pressure is 2500 mbar for all tests; pressure ~2500 (2490–2510) during steps 500–1400. Aborts (9999) stop at ~1025 mbar | – | result valid only if pressure ~2500 during measuring (1200–1300) |
| 10 | Late rows: 2,459 rows arrive 2–4 days after the reading, **all in the 2025-08-01 drop, all line A** (A1 1,235, A2 1,224). This is the Line A outage 28–30 Jul 2025, backfilled; same event as assembly_summary #12. All other rows arrive the same day (lag 0). No negative lags | 2,459 | do not assume drop date = data date; incremental load must accept and insert rows for past dates |
| 11 | Units are the same in old and new format: flow 0–~20 mL/min, pressure 0–~2514 mbar, step 0–9999 in both. Flow median slightly higher in new format (~4.0 vs ~3.7): too small for a unit change, possibly slow drift over time (for anomaly detection later) | – | mapping both formats to one signal is safe; no unit conversion needed |

---

## mes/batches.csv
Notebook: `notebooks/03_mes_batches.ipynb` (in progress)

**One row:** one version of one batch record. Each batch is sent twice: `IN_PROGRESS` at start (no end, no
counts), then a final record (`COMPLETED` / `CANCELLED`) at the end. The latest version (`record_updated_at`) is
the true one.
**Rows:** 2,749 from 717 drops → **1,376 distinct batch IDs** (1,373 real batches + 3 test/placeholder).

| # | Finding | Rows | Silver rule |
|---|---|---|---|
| 1 | File missing in 14 drops: the same 12 as signals (Christmas shutdowns, 2026-10-01) plus 2025-02-06 and 2025-04-20 | 14 drops | loader skips missing files; to check: why the 2 extra dates |
| 2 | Each real batch has exactly 2 records (`IN_PROGRESS` + final) | 1,373 batches | keep the latest record per batch by `record_updated_at` |
| 3 | 3 single-record batches are not real: `B000000`, `B000001` (status `TEST`) and `NA-PENDING` (no status). All line B, start at exactly 08:00:00, no end | 3 | quarantine ("test batch" / "pending ID"); exclude from matching |
| 4 | Status of final records: `COMPLETED` 1,360, `CANCELLED` 13 | 1,373 | – |
| 5 | Duration of `COMPLETED` batches: 19 h to 1 d 18 h, median ~1 d 6 h | 1,360 | batch window = `batch_start` to `batch_end` of the final record |
| 6 | All 13 `CANCELLED` batches: 7 min to ~15 h long, 0 tubs, 0 good, 0 rejects. **Every comment says "Batch cancelled - filter integrity failure on replacement assembly".** Clustered: 6 in Jan 2026, 7 between 30 Mar and 3 Apr 2026 | 13 | **D-012:** include in assembly matching (they are the deviations to investigate); exclude from product impact |
| 7 | Counts per `COMPLETED` batch: tubs 1,723–3,184 (median ~2,400); good units 274,367–506,815 (median ~381,000); rejects 576–3,907 (median ~1,860, about 0.5% of good) | 1,360 | convert to numbers (text sums join strings); reference ranges for later anomaly checks |
| 8 | Counts are text after loading (`dtype=str`); summing text joins the strings ("2168"+"1779" = "21681779") with no error | – | convert count columns to numeric in silver |

