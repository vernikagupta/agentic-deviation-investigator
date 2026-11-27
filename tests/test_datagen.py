"""Acceptance tests for the synthetic dataset.

They check three things:
1. Integrity: IDs join across systems the way a real investigation needs.
2. Label isolation: no ground truth leaks into data/raw.
3. Detectability: every planted scenario is visible in the RAW data, so the
   pipeline and agents have a fair chance to find it.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from datagen import config as C
from datagen.generate import main

DAY = pd.Timedelta(days=1)
START = pd.Timestamp(C.START, tz="UTC")


@pytest.fixture(scope="module")
def data(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("data")
    main(out)
    return out


def summary(data: Path) -> pd.DataFrame:
    """Minimal cleaning of the historian assembly summary, enough for checks."""
    files = sorted((data / "raw/historian/assembly_summary").glob("*.csv"))
    df = pd.concat([pd.read_csv(f, dtype=str) for f in files]).drop_duplicates()
    df = df[df.Attempts.astype(int) > 0]
    df["cart"] = "FITC-" + df.Cart.str.extract(r"([ABC][12])$")[0]
    df["start"] = pd.to_datetime(df.FIT_Cycle_Window.str[:19], utc=True)
    for col in ["PreIT_Flow", "PUPSIT_Flow"]:
        df[col] = pd.to_numeric(df[col].replace("-", np.nan))
    return df.sort_values("start")


def window(scen: str, end_key: str = "fix_day"):
    s = C.SCENARIOS[scen]
    return START + s["start_day"] * DAY, START + s.get(end_key, s.get("end_day")) * DAY


def test_label_isolation(data):
    for f in (data / "raw").rglob("*.csv"):
        head = f.read_text()[:20000]
        assert "scenario" not in head.lower(), f
        assert not re.search(r"\bS[1-9]_|RH1_", head), f


def test_ids_join_across_systems(data):
    b = pd.read_csv(data / "raw/mes/batches.csv", dtype=str)
    m = pd.read_csv(data / "raw/erp/material_consumption.csv", dtype=str)
    assert set(m.batch_id) <= set(b.batch_id)
    eq = pd.read_csv(data / "reference/equipment_master.csv")
    assert set(C.CARTS) <= set(eq.equipment_id)
    assert (b.batch_id == "B000000").any()  # dummy batch trap present


def test_messy_traps_present(data):
    s = pd.concat(pd.read_csv(f, dtype=str) for f in (data / "raw/historian/assembly_summary").glob("*.csv"))
    assert s.duplicated().any(), "overlapping exports should create duplicates"
    assert (s.PreIT_Flow == "-").any() and s.Wetting_Time.str.endswith(" s").any()
    assert s.Cart.nunique() > len(C.CARTS), "cart aliases should vary"
    env = pd.read_csv(data / "raw/environment/room_conditions.csv")
    assert set(env.temperature_unit) == {"C", "F"}
    wo = pd.read_csv(data / "raw/cmms/work_orders.csv")
    assert wo.location.str.contains("FITC-0").any() and wo.longdescription.str.startswith("<").all()


def test_s1_cart_drift_detectable(data):
    df = summary(data)
    lo, hi = window("S1_cart_seal_wear")
    sub = df[(df.cart == "FITC-B2") & (df.start >= lo) & (df.start < hi)].dropna(subset=["PUPSIT_Flow"])
    slope, _, _, p, _ = stats.linregress(np.arange(len(sub)), sub.PUPSIT_Flow)
    assert slope > 0.03 and p < 0.01


def test_s5_sensor_drift_detectable(data):
    df = summary(data)
    lo, _ = window("S5_sensor_drift")
    # From day 50 the bad filter lot (S2) also hits line C and partly masks the
    # drift - a deliberate overlap. Check the clean part of the window.
    hi = START + C.SCENARIOS["S2_bad_filter_lot"]["start_day"] * DAY
    sub = df[(df.cart == "FITC-C1") & (df.start >= lo) & (df.start < hi)].dropna(subset=["PUPSIT_Flow"])
    slope, _, _, p, _ = stats.linregress(np.arange(len(sub)), sub.PUPSIT_Flow)
    assert slope < 0 and p < 0.05


def test_s2_bad_lot_elevates_pupsit(data):
    truth = pd.read_csv(data / "eval/assembly_truth.csv")
    df = summary(data).merge(truth[["cart_id", "build_start", "filter_lot"]].assign(
        start=lambda t: pd.to_datetime(t.build_start, utc=True)), left_on=["cart", "start"],
        right_on=["cart_id", "start"])
    bad = df[df.filter_lot == "VL2-0719"].PUPSIT_Flow.mean()
    rest = df[df.filter_lot != "VL2-0719"].PUPSIT_Flow.mean()
    assert bad - rest > 0.6


def test_s4_autoclave_overtemp_visible(data):
    c = pd.read_csv(data / "raw/autoclave/cycles.csv", parse_dates=["cycle_start"])
    lo, hi = window("S4_autoclave_overtemp")
    hot = c[(c.autoclave_id == "AC-02") & (c.cycle_start >= lo) & (c.cycle_start < hi)]
    assert (hot.max_chamber_temp_c > 126).all() and len(hot) > 3
    assert (c[c.autoclave_id == "AC-01"].max_chamber_temp_c < 125).all()


def test_station_scenarios_visible(data):
    f = pd.read_csv(data / "raw/line/filling_checks.csv", parse_dates=["check_time"])
    f["fill_weight_mg"] = pd.to_numeric(f.fill_weight_mg)
    lo, hi = window("S8_filler_needle_underfill")
    late = f[(f.line == "B") & (f.check_time >= hi - 4 * DAY) & (f.check_time < hi)]
    gap = late[late.needle != 7].fill_weight_mg.mean() - late[late.needle == 7].fill_weight_mg.mean()
    assert gap > 15
    v = pd.read_csv(data / "raw/line/stoppering_checks.csv", parse_dates=["check_time"])
    lo, hi = window("S9_vacuum_pump_degradation")
    a = v[v.line == "A"]
    assert a[(a.check_time >= hi - 3 * DAY) & (a.check_time < hi)].vacuum_mbar_abs.mean() > 140
    t = pd.read_csv(data / "raw/line/tyvek_removal_alarms.csv", parse_dates=["alarm_time"])
    lo, hi = window("S7_tyvek_gripper_wear")
    ta = t[t.line == "A"]
    assert len(ta[(ta.alarm_time >= hi - 4 * DAY) & (ta.alarm_time < hi)]) > 5 * len(
        ta[(ta.alarm_time >= hi + 4 * DAY) & (ta.alarm_time < hi + 8 * DAY)])


def test_signals_have_step_profile(data):
    f = sorted((data / "raw/historian/test_signals").glob("FITC_A1_*.csv"))[0]
    s = pd.read_csv(f)
    steps = set(s.filter(like="StepIndex").iloc[:, 0])
    assert {0, 100, 1200, 1300, 1400}.issubset(steps)
    hold = s[s.filter(like="StepIndex").iloc[:, 0] == 1200].filter(like="Pressure").iloc[:, 0]
    assert abs(hold.median() - C.SPEC["test_pressure_mbar"]) < 100
