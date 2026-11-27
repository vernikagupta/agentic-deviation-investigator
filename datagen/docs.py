"""Fictional SOPs and troubleshooting guides for the knowledge (RAG) agent.

Written from general public knowledge of sterile filtration and syringe
filling. No real company procedures, limits or equipment are described.
"""

from __future__ import annotations

from pathlib import Path

from . import config as C

S = C.SPEC

DOCS = {
    "SOP-FIT-001_filter_integrity_testing.md": f"""---
doc_id: SOP-FIT-001
title: Filter Integrity Testing on Integrity Test Carts
version: 3.0
status: fictional training document
---
# Purpose
Define how sterilizing-grade filter assemblies are integrity tested before and after use.

# Test sequence per batch
1. Build the single-use filter assembly and connect it to the integrity test cart.
2. Wet the membrane with water for injection. Minimum wetting time: {S['wetting_min_s']} s.
3. Run the pre-use integrity test (Pre-IT, diffusion method). Limit: <= {S['pre_it_max_ml_min']} mL/min.
4. Sterilize the assembly in the autoclave (121-124 C, minimum 30 min hold).
5. Re-wet the membrane (sterilization dries it). Minimum wetting time: {S['wetting_min_s']} s.
6. Run PUPSIT (pre-use post-sterilization integrity test). Limit: <= {S['pupsit_max_ml_min']} mL/min.
7. Use the assembly for filtration during the batch.
8. After the batch, run the post-use integrity test. Limit: <= {S['post_use_max_ml_min']} mL/min.

# Test pressure
Diffusion tests are run at {S['test_pressure_mbar']} mbar. The test recipe steps are recorded by the cart
as StepIndex values. The final diffusion flow is valid at StepIndex 1300 (test complete).

# Failed test
- A failed test may be repeated up to 2 more times (3 attempts in total).
- Before repeating: check connections, check wetting time, re-wet if wetting was short.
- If all attempts fail, the filter assembly is rejected, a deviation is raised, and a new assembly is built.
- A test that aborts (StepIndex 9999) is not a result. The cart reports flow 0. Repeat the test.
""",
    "TRB-FIT-002_integrity_test_troubleshooting.md": """---
doc_id: TRB-FIT-002
title: Troubleshooting Integrity Test Failures
version: 1.4
status: fictional training document
---
# Common causes of high diffusion flow
| Pattern | Likely cause | What to check |
|---|---|---|
| First attempt fails, passes after re-wetting | Incomplete wetting (before Pre-IT or before PUPSIT) | Wetting time of that test, wetting method, crew |
| Fails on one cart across many filter lots | Cart leak (seals, fittings) or cart hardware | Cart leak test, seal condition, recent maintenance |
| Fails on several carts using the same filter lot | Filter lot defect | Filter lot, supplier certificate, incoming inspection |
| Pre-IT normal but PUPSIT high | Damage during sterilization | Autoclave cycle record: temperature, hold time |
| Readings slowly decreasing on one cart | Transducer drift (risk: real failures masked) | Calibration status |
| Small rise on all carts of one line | Room temperature change | Room conditions log |

# Notes
- Marginal failures (just above the limit) are often caused by test conditions, not a defective filter.
- Pressure that drops during the stabilization step points to a gas leak in the cart or connections.
- Always compare against the cart's own history; carts differ slightly from each other.
""",
    "SOP-MNT-004_test_cart_maintenance.md": """---
doc_id: SOP-MNT-004
title: Integrity Test Cart Maintenance and Calibration
version: 2.1
status: fictional training document
---
# Preventive maintenance
- Calibration (PMCAL) of pressure transducer and flow meter approximately every 60-75 days.
- Inspect inlet seals and manifold fittings at each calibration.

# Corrective maintenance triggers
- Repeated test failures on one cart while other carts pass with the same filter lots.
- Rising diffusion flow trend on one cart.
- Pressure decay during the stabilization step.

# After maintenance
- Run a leak test and a reference filter test before releasing the cart.
- A cart's statistical baseline should be re-established after a seal replacement or recalibration.
""",
    "SOP-TRR-006_tyvek_removal.md": """---
doc_id: SOP-TRR-006
title: Tub Debagging and Tyvek Lid Removal
version: 1.2
status: fictional training document
---
# Process
Tubs of 160 nested syringes (10 x 16) arrive double-bagged. Bags are removed at successive cleanroom
grades. Inside the isolator, the Tyvek removal robot lifts the lid and the inner liner with vacuum cups.

# Alarms
- TRR-101 LID_NOT_REMOVED: lid still present after the removal cycle.
- TRR-102 LINER_TEAR: liner torn, fragments may remain.
- TRR-103 CUP_VACUUM_LOW: vacuum cups not holding; check cup wear and vacuum supply.

# Impact
Tyvek removal alarms cause line stoppages. They do not affect the filtration step or product sterility
when cleared per procedure.
""",
    "SOP-FIL-007_filling_and_fill_weight.md": f"""---
doc_id: SOP-FIL-007
title: Rotary Filler Operation and Fill Weight Checks
version: 2.0
status: fictional training document
---
# Fill weight checks
- Every 30 minutes, one syringe per needle (10 needles) is weighed.
- Target weight depends on the product fill volume. Tolerance: +/- {S['fill_weight_tolerance_pct']}% of target.
- Always compare against the target recorded with the check, because products differ (1.0 mL and 0.5 mL).

# Low weights on one needle
- Usually a dosing pump issue on that needle (piston or seal wear).
- Low weights on all needles at once point to an upstream supply problem, such as flow restriction.
""",
    "SOP-STP-008_vacuum_stoppering.md": f"""---
doc_id: SOP-STP-008
title: Vacuum Stoppering
version: 1.5
status: fictional training document
---
# Process
After filling, the plunger stopper is placed under vacuum to minimise the air bubble.

# Checks every 30 minutes per station
- Vacuum level: <= {S['stopper_vacuum_max_mbar_abs']} mbar absolute.
- Plunger depth: {S['plunger_depth_min_mm']} - {S['plunger_depth_max_mm']} mm.

# Weak vacuum
Rising vacuum level and more variable plunger depth point to the vacuum pump losing capacity
(vane or oil condition). Schedule pump service.
""",
}


def write_docs(out: Path) -> None:
    d = out / "docs"
    d.mkdir(parents=True, exist_ok=True)
    for name, text in DOCS.items():
        (d / name).write_text(text)
