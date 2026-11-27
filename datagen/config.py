"""Configuration for the synthetic sterile syringe fill line (v2).

Everything here is fictional: site, lines, equipment IDs, vendors, products,
spec limits. Values are plausible, not taken from any real plant.

The simulation has two layers:
1. Truth  - what physically happened (clean, internal to the generator).
2. Export - what each source system delivers, as daily drops (messy).

Scenario definitions live here so the whole story of the dataset can be read in
one place. Day numbers are offsets from START.
"""

from __future__ import annotations

import datetime as dt

SEED = 42
START = dt.datetime(2024, 10, 1, 6, 0)  # UTC
DAYS = 730                              # 1 Oct 2024 - 30 Sep 2026

LINES = ["A", "B", "C"]

# Two integrity-test carts per line: formulation filtration and final-fill filtration.
CART_ROLES = {"1": "formulation", "2": "fill"}
CARTS = [f"FITC-{line}{n}" for line in LINES for n in CART_ROLES]

AUTOCLAVE_FOR_LINE = {"A": "AC-01", "B": "AC-02", "C": "AC-02"}

PRODUCTS = {
    "A": [("PRD-210", 1.0), ("PRD-215", 1.0)],
    "B": [("PRD-320", 1.0)],
    "C": [("PRD-410", 1.0), ("PRD-412", 0.5)],  # (product, fill volume mL)
}
FILL_DENSITY_MG_PER_ML = 1020

SYRINGES_PER_TUB = 160  # 10 x 16 nest
FILLER_NEEDLES = 10
STOPPER_STATIONS = ["ST-1", "ST-2"]
CREWS_PER_LINE = 4      # crews rotate: 2 days on, day/night shifts

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
    "filter_bubble_point_min_bar": 3.2,
}

# Healthy baseline per cart: (pre-IT median, pre-IT log-sd, PUPSIT median, PUPSIT log-sd).
# Flows are log-normal with an extra right tail -> NOT normally distributed.
BASELINE = {
    "FITC-A1": (0.70, 0.10, 2.70, 0.08),
    "FITC-A2": (0.74, 0.11, 2.85, 0.085),
    "FITC-B1": (0.68, 0.10, 2.65, 0.08),
    "FITC-B2": (0.72, 0.11, 2.80, 0.085),
    "FITC-C1": (0.71, 0.10, 2.75, 0.08),
    "FITC-C2": (0.76, 0.11, 2.95, 0.09),
}
TAIL_RATE = 0.03  # share of tests with an extra right-tail bump

# Normal cart aging: seals slowly relax, flows creep up until the yearly seal kit PM.
AGING_PER_ASSEMBLY = {"pre": 0.0003, "pup": 0.0015}
SEAL_KIT_PM_DAYS = [300, 665]  # approx day of yearly seal kit replacement per cart (+/- jitter)

FILTER_VENDORS = {
    "V-FLT-01": {"name": "Filtra Membranes (fictional)", "share": 0.6},
    "V-FLT-02": {"name": "Membrex Separations (fictional)", "share": 0.4},
}
LOT_ROTATION_DAYS = 12

SITE_SHUTDOWNS = [(85, 92), (450, 457)]  # year-end shutdowns, all lines
PLANNED_SHUTDOWNS = {"A": [(230, 233), (600, 603)], "B": [(260, 263), (630, 633)], "C": [(290, 293), (515, 518)]}

# ---------------------------------------------------------------------------
# Scenarios (ground truth). Only the generator and data/eval/ know these.
# ---------------------------------------------------------------------------
SCENARIOS = {
    "S5_sensor_drift": {
        "type": "measurement", "entity": "FITC-C1", "start_day": 120, "fix_day": 170,
        "reported_factor_per_day": -0.007,
        "cause": "Flow/pressure transducer on cart FITC-C1 drifting low; reported flows fall until "
                 "recalibration (PMCAL). Risk: real failures can be masked.",
        "root_cause_class": "measurement",
    },
    "S7_tyvek_gripper_wear": {
        "type": "equipment_degradation", "entity": "TRR-A", "start_day": 200, "fix_day": 212,
        "alarm_rate_peak": 0.06,
        "cause": "Vacuum cups on Tyvek removal robot TRR-A wearing out; rising lid removal alarms and "
                 "downtime, no product impact.",
        "root_cause_class": "equipment",
    },
    "S1_cart_seal_wear": {
        "type": "equipment_degradation", "entity": "FITC-B2", "start_day": 380, "fix_day": 408,
        "pupsit_slope_per_assembly": 0.085, "pre_it_slope_per_assembly": 0.010,
        "cause": "Worn inlet seal on cart FITC-B2 causing a growing gas leak during integrity tests; "
                 "fixed by corrective work order replacing the seal.",
        "root_cause_class": "equipment",
    },
    "RH1_new_lot_coincidence": {
        "type": "red_herring", "entity": "VL1-1016", "vendor": "V-FLT-01", "start_day": 379, "end_day": 392,
        "lines": ["A", "B"],
        "cause": "New filter lot introduced around the start of S1. Normal results on every cart except "
                 "FITC-B2 - the lot is NOT the cause.",
        "root_cause_class": "none",
    },
    "S8_filler_needle_underfill": {
        "type": "equipment_degradation", "entity": "FILLER-B needle 7", "start_day": 386, "fix_day": 406,
        "max_bias_mg": -30.0,
        "cause": "Dosing pump for needle 7 on FILLER-B wearing; fill weight drifts low. Overlaps S1 in time "
                 "but unrelated to the filter cart.",
        "root_cause_class": "equipment",
    },
    "S2_bad_filter_lot": {
        "type": "supplier_lot", "entity": "VL2-0115", "vendor": "V-FLT-02", "start_day": 470, "end_day": 484,
        "lines": ["A", "C"], "pupsit_shift": (0.7, 1.7), "pre_it_shift": (0.10, 0.25),
        "cause": "Filter capsule lot VL2-0115 from V-FLT-02 had a membrane defect; elevated PUPSIT on every "
                 "cart that used it; re-testing does not help. Lot passed incoming inspection.",
        "root_cause_class": "supplier",
    },
    "S4_autoclave_overtemp": {
        "type": "process_equipment", "entity": "AC-02", "start_day": 545, "fix_day": 549,
        "max_temp_c": (127.0, 129.5), "pupsit_shift": (1.3, 2.2),
        "cause": "Autoclave AC-02 temperature controller overshoot damaged filter membranes during "
                 "sterilization: pre-IT normal, PUPSIT high. Lines B and C.",
        "root_cause_class": "process_equipment",
    },
    "S3_incomplete_wetting": {
        "type": "procedural", "entity": "Line C crew 4", "base_rate": 0.03, "crew_rate": 0.22,
        "line": "C", "crew": "C-CREW4", "start_day": 600, "end_day": 640,
        "cause": "Newly formed crew 4 on line C shortened manual wetting; first pre-IT attempt fails high and "
                 "passes after re-wetting. Not a filter or cart defect.",
        "root_cause_class": "procedure",
    },
    "S6_warm_room": {
        "type": "benign_environment", "entity": "LINE-A room", "start_day": 650, "end_day": 658,
        "temp_c": (25.0, 27.5),
        "cause": "HVAC adjustment raised line A room temperature; diffusion flows rise slightly but stay in "
                 "spec. Expected behaviour, not a fault.",
        "root_cause_class": "benign",
    },
    "S9_vacuum_pump_degradation": {
        "type": "equipment_degradation", "entity": "VAC-A", "start_day": 680, "fix_day": 695,
        "max_vacuum_rise_mbar": 85.0,
        "cause": "Vacuum pump VAC-A at the line A stoppering station losing capacity; weaker vacuum and more "
                 "variable plunger depth until pump service.",
        "root_cause_class": "equipment",
    },
    "S10_seal_wear_recurrence": {
        "type": "equipment_degradation", "entity": "FITC-A2", "start_day": 700, "fix_day": 726,
        "pupsit_slope_per_assembly": 0.085, "pre_it_slope_per_assembly": 0.010,
        "cause": "Same failure mode as S1, now on cart FITC-A2. A closed past deviation (S1) documents the "
                 "same pattern and fix - an investigator with memory of past cases should find it.",
        "root_cause_class": "equipment",
    },
}

# Export behaviour (daily drops)
SCHEMA_CHANGE_DAY = 365          # historian software upgrade: columns and tag names change
CMMS_FAILURECODE_DAY = 500       # CMMS adds a failure code column
HISTORIAN_OUTAGE = (300, 303)    # line A historian exports missing, backfilled later
HISTORIAN_LATE_RATE = 0.02       # assembly rows delivered 1-3 days late
HISTORIAN_RESEND_RATE = 0.01     # rows delivered twice
ERP_CORRECTION_RATE = 0.03       # wrong lot posted, then reversed and re-posted

# Base rates for normal operations.
FAULTED_TEST_RATE = 0.015
RANDOM_CONNECTION_FAIL = 0.02
EMPTY_ASSEMBLY_ROWS = 0.01
MISSING_DASH_RATE = 0.02
VENDOR_LOT_BLANK_RATE = 0.45
TYVEK_BASE_ALARM_RATE = 0.004
