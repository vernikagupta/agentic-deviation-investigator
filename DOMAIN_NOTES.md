# Domain Notes: Prefilled-Syringe (PFS) Fill Line

Fictional plant, synthetic data. Notes from discovery interviews with the process engineer.
Each step lists what happens and why. See `PROBLEM_STATEMENT.md` for the problem being solved.

## 1. The line
- 3 lines (A, B, C). Each line has two filter integrity test carts:
  - **Cart 1:** filters the formulation (drug solution) when it is transferred.
  - **Cart 2:** the final sterilizing filter, just before the filler.
- 4 crews per line, day and night shifts, rotating every 2 days.

## 2. The filter
- **What:** a sterilizing-grade filter capsule: a 0.2 µm PES (polyethersulfone) membrane in a plastic housing.
- **Why:** it removes bacteria from the drug solution. The products cannot be heat-sterilized after filling,
  because heat would damage the drug. So the solution is sterilized by filtration and kept sterile afterwards.
- **Single-use:** a new filter for every batch, discarded after the batch. Never cleaned or reused.
  - So filters do not wear out. Equipment around them does (carts, sensors, autoclave).
- **Assembly:** the capsule plus tubing and connectors. Built by the operator and connected to the test cart.
- **Lots and suppliers:** filters come from two suppliers. Each delivery is a lot.
  QC checks the supplier certificate at receipt. A lot can pass this check and still be defective.

## 3. The integrity test (diffusion method)
- **Why:** a damaged membrane looks the same as a good one. The test is the only proof the filter is intact.
- **How:**
  1. The membrane is wetted, so water fills the pores.
  2. The cart applies gas pressure (2500 mbar) on one side.
  3. Intact membrane: only a small amount of gas dissolves in the water and passes through slowly. Low flow.
  4. Damaged membrane: gas passes through the open path. High flow.
  5. The cart measures the flow in mL/min and compares it to the limit.
- **High flow does not always mean a bad filter.** It can also come from:
  - a leak in the cart (for example a worn seal),
  - a bad connection,
  - a membrane that was not fully wetted,
  - a sensor reading wrong (a sensor drifting low can also hide a real failure).
  - This is why investigations are hard.

## 4. One batch, step by step

### Filter preparation (about 5 to 6.5 hours)
| Step | What | Why |
|---|---|---|
| 1. Build | Operator builds two assemblies, one per cart. | A new sterile path for every batch. |
| 2. Wet | Wet the membrane with water for injection, at least 60 s. | The diffusion test only works on a fully wet membrane. Short wetting gives falsely high flow. |
| 3. Pre-IT | Integrity test before sterilization. Limit ≤ 1.6 mL/min. | Catches a filter damaged in manufacturing or transport, or a wrong build, before spending 3 to 4 hours on sterilization. A failure here is cheap. |
| 4. Autoclave | Steam-sterilize both assemblies together. 121 to 124 °C, at least 30 min hold. | The filter sterilizes the solution, but everything after the filter (housing outlet, tubing, connectors) must also be sterile. |
| 5. Re-wet | Wet the membrane again. | Sterilization dries the membrane. |
| 6. PUPSIT | Integrity test after sterilization, before use. Limit ≤ 4.2 mL/min. | Steam (heat, pressure changes, drying) or handling can damage the membrane. Regulators expect this test (EU GMP Annex 1). Flows are naturally higher after sterilization, so the limit is higher. |

### Filling (about 18 to 28 hours)
| Step | What | Why it is monitored |
|---|---|---|
| 7. Tubs | Sterile syringes arrive in tubs: 160 per tub (10 × 16 nest), sealed with a Tyvek lid. | |
| 8. Tyvek removal robot | Removes the lid and liner inside the isolator. | Alarms (lid not removed, liner tear, low cup vacuum) cause stops and downtime. |
| 9. Rotary filler | 10 needles fill the syringes. Fill weight checked per needle every 30 min. Target 1.0 mL or 0.5 mL depending on product. | Underfill or overfill is a quality defect. A worn dosing pump affects one needle. |
| 10. Vacuum stoppering | Two stations pull a vacuum and push the plunger stopper in. Vacuum and plunger depth checked every 30 min. | Weak vacuum gives wrong plunger depth. |

### After filling
| Step | What | Why |
|---|---|---|
| 11. Post-use test | Integrity test after filtration. Limit ≤ 4.5 mL/min. | Proves the filter stayed intact during the whole filtration. If it fails, every syringe filled through that filter is at risk. |

### Timing
Typical times per batch on one line. They vary from batch to batch.

**Filter preparation**
| Step | Typical time | Note |
|---|---|---|
| Build both assemblies | 30 to 55 min | The second cart starts 0 to 20 min after the first. |
| Wetting | 80 to 110 s | Minimum 60 s. Short wetting (25 to 55 s) gives falsely high results. |
| Pre-IT (one attempt) | about 3 min | 170 to 200 s. |
| Retest after a failed attempt | +4 to 9 min | Short wetting: re-wet (85 to 115 s) plus 2 min, then retest. |
| Wait for autoclave | 15 to 35 min | Starts after both Pre-ITs are done. |
| **Autoclave cycle** | **about 3.5 to 4 h** | Heat-up and air removal (~45 min), hold (30 to 33 min), cool-down and drying (2.5 to 3 h). |
| Wait after autoclave | 10 to 45 min | |
| Re-wetting | 80 to 110 s, plus 1 min | |
| PUPSIT (one attempt) | about 3 min | |
| **Total preparation** | **about 5 to 6.5 h** | Mostly the autoclave. |

**Filling and after**
| Step | Typical time |
|---|---|
| Wait before filling | 15 to 40 min |
| **Filling** | **18 to 28 h** |
| Wait after filling | 10 to 45 min |
| Post-use test | about 3 min per attempt |

**Complete batch**
- First assembly build to end of post-use test: **about 24 to 36 h**.
- Changeover before the next batch (cleaning, line clearance, staging): **5 to 10 h**.
- One line starts a new batch about every **1.5 days**.

**Batch size (one tub is not one batch)**
- One tub = 160 syringes. The line fills about **95 to 115 tubs per hour** (one tub every ~35 s),
  about **16,000 syringes per hour**.
- One batch (18 to 28 h of filling) = about **1,700 to 3,200 tubs** = about **280,000 to 510,000 syringes**.
- **Why it matters:** if a post-use test fails, a few hundred thousand syringes are at risk. One filter
  failure is expensive.

**When something fails**
- Retests add minutes.
- A replacement assembly adds **about 5 to 6 h** (its own build, Pre-IT and a separate autoclave cycle).
- A cancelled batch has no filling; it ends after the replacement fails.

## 5. When a test fails
1. Operator checks connections and wetting, re-wets if wetting was short, then retests. Maximum 3 attempts.
2. All 3 fail: the assembly is rejected, a deviation is opened in QMS, and a replacement assembly is built and tested.
3. The replacement also fails: the batch is cancelled.
- **Why up to 3 attempts:** many first failures come from setup (connection, wetting), not from the filter.

## 6. What the test pattern suggests
| Pattern | Points towards |
|---|---|
| Pre-IT normal, PUPSIT high | Autoclave, or something between the two tests. |
| Pre-IT and PUPSIT both high | Filter lot, cart leak, or wetting. |
| First attempt high, retest passes after re-wetting | Incomplete wetting (procedure). |
| High on every cart that used one lot | Filter lot (supplier). |
| High on one cart only, rising over many batches | Cart (for example seal wear). |
| Flows slowly falling on one cart | Sensor drift. Real failures may be hidden. |

These are starting points, not conclusions. Several causes can overlap in time, so each must be checked
and ruled in or out with evidence.

## 7. QMS (Quality Management System)
- **What:** software where the quality team records quality events. The main record here is a **deviation**:
  something that did not follow the procedure or the spec.
- **Why it matters:** a filter integrity test that fails all 3 attempts must be recorded as a deviation.
- **Two stages:**
  - **Open:** what happened, line, batch, equipment, and an initial assessment (first guess, can be wrong).
  - **Closed:** confirmed root cause and corrective action. Takes 2 to 6 weeks.
- QMS also holds CAPAs (corrective and preventive actions) and change controls.
- QA owns QMS. A deviation cannot be closed without QA approval.
- Closed deviations are a record of past cases. The same failure can recur on another cart.

## 8. Source systems
See `DATA_OVERVIEW.md` (9 source systems, delivery and recording frequency).

## 9. References
- Video, PFS filling machine with 2 robots (same process as this line: Tyvek removal, filling,
  stoppering): https://www.youtube.com/watch?v=-qN8DD8A3Do
