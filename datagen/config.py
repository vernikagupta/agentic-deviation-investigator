"""Configuration for the synthetic sterile syringe fill line.

Everything here is fictional: site, lines, equipment IDs, vendors, products,
spec limits. Values are chosen to be plausible, not taken from any real plant.

The simulation has two layers:
1. Truth  - what physically happened (clean, internal to the generator).
2. Export - what each source system records (messy, written to data/raw).

Scenario definitions live here so the whole "story" of the dataset can be read
in one place. Day numbers are offsets from START.
"""

from __future__ import annotations

import datetime as dt

SEED = 42
START = dt.datetime(2026, 6, 1, 6, 0)  # UTC
DAYS = 120

LINES = ["A", "B", "C"]

# Two integrity-test carts per line: one for formulation filtration (vessel ->
# sterile surge vessel), one for final-fill filtration (surge vessel -> filler).
CART_ROLES = {"1": "formulation", "2": "fill"}
CARTS = [f"FITC-{line}{n}" for line in LINES for n in CART_ROLES]

# Autoclave used for each line's filter assemblies.
AUTOCLAVE_FOR_LINE = {"A": "AC-01", "B": "AC-02", "C": "AC-02"}

PRODUCTS = {
    "A": [("PRD-210", 1.0), ("PRD-215", 1.0)],
    "B": [("PRD-320", 1.0)],
    "C": [("PRD-410", 1.0), ("PRD-412", 0.5)],  # (product, fill volume mL)
}
FILL_DENSITY_MG_PER_ML = 1020  # fill weight target = volume * density

SYRINGES_PER_TUB = 160  # 10 x 16 nest
FILLER_NEEDLES = 10
STOPPER_STATIONS = ["ST-1", "ST-2"]

# Fictional spec limits (diffusion flow in mL/min).
SPEC = {
    "pre_it_max_ml_min": 1.6,
    "pupsit_max_ml_min": 4.2,
    "post_use_max_ml_min": 4.5,
    "wetting_min_s": 60,
    "test_pressure_mbar": 2500,
    "fill_weight_tolerance_pct": 2.0,
    "stopper_vacuum_max_mbar_abs": 150,
    "plunger_depth_min_mm": 7.5,
    "plunger_depth_max_mm": 8.5,
    "autoclave_temp_min_c": 121.0,
    "autoclave_temp_max_c": 124.0,
}

# Healthy baseline per cart: (pre-IT mean, pre-IT sd, PUPSIT mean, PUPSIT sd).
BASELINE = {
    "FITC-A1": (0.70, 0.07, 2.70, 0.22),
    "FITC-A2": (0.74, 0.08, 2.85, 0.24),
    "FITC-B1": (0.68, 0.07, 2.65, 0.21),
    "FITC-B2": (0.72, 0.08, 2.80, 0.23),
    "FITC-C1": (0.71, 0.07, 2.75, 0.22),
    "FITC-C2": (0.76, 0.08, 2.95, 0.25),
}

# Fictional filter vendors and their lot rotation.
FILTER_VENDORS = {
    "V-FLT-01": {"name": "Filtra Membranes (fictional)", "share": 0.6},
    "V-FLT-02": {"name": "Membrex Separations (fictional)", "share": 0.4},
}
LOT_ROTATION_DAYS = 10

# ---------------------------------------------------------------------------
# Scenarios (ground truth). Only the generator and data/eval/ know these.
# ---------------------------------------------------------------------------
SCENARIOS = {
    "S1_cart_seal_wear": {
        "type": "equipment_degradation",
        "entity": "FITC-B2",
        "start_day": 35,
        "fix_day": 62,
        "pupsit_slope_per_assembly": 0.085,
        "pre_it_slope_per_assembly": 0.010,
        "cause": "Worn inlet seal on cart FITC-B2 causing a growing gas leak during "
        "integrity tests; fixed by corrective work order replacing the seal.",
        "root_cause_class": "equipment",
    },
    "S2_bad_filter_lot": {
        "type": "supplier_lot",
        "entity": "VL2-0719",
        "vendor": "V-FLT-02",
        "start_day": 50,
        "end_day": 64,
        "lines": ["A", "C"],
        "pupsit_shift": (0.7, 1.7),
        "pre_it_shift": (0.10, 0.25),
        "cause": "Filter capsule lot VL2-0719 from V-FLT-02 had a membrane defect; "
        "elevated PUPSIT flow on every cart that used it, re-testing does not help.",
        "root_cause_class": "supplier",
    },
    "S3_incomplete_wetting": {
        "type": "procedural",
        "entity": "all carts (concentrated on line C)",
        "base_rate": 0.03,
        "line_c_rate": 0.18,
        "line_c_start_day": 80,
        "line_c_end_day": 95,
        "cause": "Short manual wetting time leaves the membrane partly dry; first "
        "pre-IT attempt fails high, passes after re-wetting. Not a real defect.",
        "root_cause_class": "procedure",
    },
    "S4_autoclave_overtemp": {
        "type": "process_equipment",
        "entity": "AC-02",
        "start_day": 71,
        "fix_day": 75,
        "max_temp_c": (127.0, 129.5),
        "pupsit_shift": (1.3, 2.2),
        "cause": "Autoclave AC-02 temperature controller overshoot damaged filter "
        "membranes during sterilization: pre-IT normal, PUPSIT high. Lines B and C.",
        "root_cause_class": "process_equipment",
    },
    "S5_sensor_drift": {
        "type": "measurement",
        "entity": "FITC-C1",
        "start_day": 20,
        "fix_day": 58,
        "reported_factor_per_day": -0.009,
        "cause": "Flow/pressure transducer on cart FITC-C1 drifting low; reported "
        "flows decrease over time until recalibration (PMCAL). Risk: masks real "
        "failures.",
        "root_cause_class": "measurement",
    },
    "S6_warm_room": {
        "type": "benign_environment",
        "entity": "LINE-A room",
        "start_day": 88,
        "end_day": 96,
        "temp_c": (25.0, 27.5),
        "cause": "HVAC adjustment raised line A room temperature; diffusion flows "
        "rise slightly but stay in spec. Expected behaviour, not a fault.",
        "root_cause_class": "benign",
    },
    "S7_tyvek_gripper_wear": {
        "type": "equipment_degradation",
        "entity": "TRR-A",
        "start_day": 40,
        "fix_day": 52,
        "alarm_rate_peak": 0.06,
        "cause": "Vacuum cups on Tyvek removal robot TRR-A wearing out; rising lid "
        "removal alarms and downtime, no product impact. Fixed by CM work order.",
        "root_cause_class": "equipment",
    },
    "S8_filler_needle_underfill": {
        "type": "equipment_degradation",
        "entity": "FILLER-B needle 7",
        "start_day": 40,
        "fix_day": 60,
        "max_bias_mg": -30.0,
        "cause": "Dosing pump for needle 7 on FILLER-B wearing; fill weight drifts "
        "low. Overlaps in time with S1 but is unrelated to the filter cart.",
        "root_cause_class": "equipment",
    },
    "S9_vacuum_pump_degradation": {
        "type": "equipment_degradation",
        "entity": "VAC-A",
        "start_day": 100,
        "fix_day": 115,
        "max_vacuum_rise_mbar": 85.0,
        "cause": "Vacuum pump VAC-A at the line A stoppering station losing "
        "capacity; weaker vacuum and more variable plunger depth until PM service.",
        "root_cause_class": "equipment",
    },
    "RH1_new_lot_coincidence": {
        "type": "red_herring",
        "entity": "VL1-0802",
        "vendor": "V-FLT-01",
        "start_day": 34,
        "end_day": 46,
        "lines": ["A", "B"],
        "cause": "New filter lot introduced around the start of S1. Used on lines A "
        "and B with normal results everywhere except FITC-B2 - the lot is NOT the "
        "cause.",
        "root_cause_class": "none",
    },
}

PLANNED_SHUTDOWNS = {"C": [(66, 69)], "A": [(30, 32)], "B": [(84, 86)]}

# Base rates for normal operations.
FAULTED_TEST_RATE = 0.015      # test aborts, historian records flow 0
RANDOM_CONNECTION_FAIL = 0.02  # first attempt fails, re-seat, pass
EMPTY_ASSEMBLY_ROWS = 0.01     # historian rows with attempts 0
MISSING_DASH_RATE = 0.02       # "-" in historian exports
VENDOR_LOT_BLANK_RATE = 0.45   # ERP rows with vendor_code but no vendor lot
TYVEK_BASE_ALARM_RATE = 0.004
