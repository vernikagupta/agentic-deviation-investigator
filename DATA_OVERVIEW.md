# Data Overview

Fictional plant, synthetic data. Notes from discovery with the process engineer: where the data lives,
how it is delivered, and how often it is recorded. For column-level details and known data problems,
see `data/README.md`.

## 1. Source systems
Each system has its own database and owner. Nothing is in one place. There are **9 source systems**:

| # | System | What it holds | Owner |
|---|---|---|---|
| 1 | **Historian** | Cart test results per assembly, post-use tests, raw pressure and flow signals, cart alarms. | Automation / OT |
| 2 | **MES** (Manufacturing Execution System) | Batch records: batch ID, line, product, crew, start/end, status, good units, rejects, comments. | Production / MES |
| 3 | **ERP** | Material postings: which filter, syringe and stopper lot went into which batch. | Supply chain / IT |
| 4 | **QC** (incoming inspection) | One record per filter lot at receipt: supplier certificate, bubble point, visual check, release. | QC lab |
| 5 | **Autoclave** | Sterilization cycles: start, end, max chamber temperature, hold time, load. | Engineering / utilities |
| 6 | **CMMS** (maintenance) | Work orders: calibrations, preventive maintenance, repairs, technician notes. | Maintenance |
| 7 | **QMS** | Deviations: open and closed, initial assessment, root cause. | QA |
| 8 | **Line stations** | Tyvek robot alarms, fill weight per needle, stoppering vacuum and plunger depth. | Production / automation |
| 9 | **Environment** | Room temperature and humidity per line, hourly. | Facilities |

Plus two non-transactional sources:
- **Equipment master:** maps each piece of equipment to its name in every system (each system names the
  same cart differently).
- **SOPs and troubleshooting guides:** from the document management system.

## 2. Delivery: how often data arrives
- **Once a day.** Each system sends one export file per day with what it has new. No direct database
  access (IT does not allow it for GMP systems).
- Not real-time: the earliest a test is visible is the next daily drop.
- Delivery problems to handle:
  - Some historian rows arrive 1 to 3 days late.
  - Some rows are delivered twice.
  - Line A historian was silent for 3 days (outage); those days arrived later in one backfill.
  - MES, CMMS and QMS send the same record twice: once at creation, once at completion or closure.

**Where it lands**
- In this repo: `data/raw/drops/YYYY-MM-DD/<system>/<file>.csv` plus a `manifest.json` per day
  (file names and row counts). A file is missing when the system had nothing new that day.
- Reference data in `data/reference/`, SOPs in `data/docs/`.
- In production: the same daily drops land in an S3 bucket.

## 3. Recording: how often each signal is sampled

### Historian test signals (`historian/test_signals.csv`)
- The cart measures every second, but the historian stores a value **only when it changes** by more than
  a set amount (deadband compression):

  | Tag | Stored when |
  |---|---|
  | StepIndex (test step number) | Every step change |
  | Pressure | Change of more than about 8 mbar, and at every step change |
  | Flow | Change of more than about 0.03 mL/min, and at every step change |

- **Result: irregular timestamps.** Many points during a pressure ramp, few during a stable hold.
- **A stored value is valid until the next stored value.** A gap does not mean missing data; it means the
  value did not change.
- Signals exist **only while a test runs** (about 3 minutes per test attempt). Nothing between tests.
- **Format:** long, one row per value: `timestamp, tag, value, quality`.
- **Tags:** three per cart (step, pressure, flow). Names changed with the historian upgrade on
  1 Oct 2025, for example `FITC_A1.Pressure` → `PLT1.LA.FITC1.PRES_MBAR`. The equipment master maps both.
- **Quality:** normally `Good`, a few values `Questionable`.
- **Valid final flow:** the value at StepIndex 1300 (test complete). StepIndex 9999 means the test aborted.

### Other data

| Data | Recorded |
|---|---|
| Assembly summary (historian) | One row per filter assembly |
| Post-use test (historian) | One row per assembly, after the batch |
| Cart alarms (historian) | When an alarm occurs |
| Fill weight | Every 30 min per needle, during filling |
| Stoppering vacuum and plunger depth | Every 30 min per station, during filling |
| Tyvek removal alarms | When an alarm occurs |
| Autoclave cycles | One row per cycle |
| Room temperature and humidity | Hourly, about 1% of hours missing |
| ERP material postings | Day after use |
| QC incoming inspection | One row per filter lot at receipt |
| MES, CMMS, QMS | At creation, and again at completion or closure |

## 4. Scale

### Production
| Unit | Size |
|---|---|
| Tub | 160 syringes (10 × 16 nest) |
| Filling speed | about 95 to 115 tubs per hour, about 16,000 syringes per hour |
| One batch | about 1,700 to 3,200 tubs, about 280,000 to 510,000 syringes |
| Batch cycle per line | about 1.5 days (preparation, filling, post-use test, changeover) |
| Filter assemblies | 2 per batch (one per cart), plus replacements after a failure |

A failed post-use test puts a whole batch (a few hundred thousand syringes) at risk.

### Dataset (2 years, 3 lines)
- About 1,370 batches and 2,780 filter assemblies.
- Fill weight: 10 needles every 30 min during filling. Stoppering: 2 stations every 30 min.
- One assembly summary row per assembly, but many signal rows per test attempt (long format).
