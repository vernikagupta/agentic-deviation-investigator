"""Acceptance tests for the synthetic dataset (v2, daily drops).

They check four things:
1. Delivery realism: daily drops, upserts, late rows, backfill, reversals, schema change.
2. Integrity: IDs join across systems the way an investigation needs.
3. Label isolation: no ground truth in data/raw.
4. Detectability: every planted scenario is visible in the RAW data.

The small loaders here are deliberately minimal and only for testing. Real
ingestion (dedupe, upsert resolution, schema mapping) is built separately.
"""

from __future__ import annotations

import json
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


def at(day: float) -> pd.Timestamp:
    return START + day * DAY


@pytest.fixture(scope="module")
def data(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("data")
    main(out)
    return out


def read_system(data: Path, rel: str) -> pd.DataFrame:
    parts = []
    for f in sorted((data / "raw/drops").glob(f"*/{rel}")):
        df = pd.read_csv(f, dtype=str, keep_default_na=False)
        df["_drop"] = f.parts[-3] if "/" in rel else f.parts[-2]
        parts.append(df)
    return pd.concat(parts, ignore_index=True)


def summary(data: Path) -> pd.DataFrame:
    """Union v1 and v2 historian summary schemas into one minimal frame."""
    df = read_system(data, "historian/assembly_summary.csv")
    v1 = df[df.get("Cart", "") != ""] if "Cart" in df else df.iloc[0:0]
    v2 = df[df.get("Equipment", "") != ""] if "Equipment" in df else df.iloc[0:0]
    u = pd.concat([
        pd.DataFrame({"cart_raw": v1.Cart, "start": v1.FIT_Cycle_Window.str[:19], "pre": v1.PreIT_Flow,
                      "pup": v1.PUPSIT_Flow, "attempts": v1.Attempts}),
        pd.DataFrame({"cart_raw": v2.Equipment, "start": v2.Cycle_Start_UTC.str[:19], "pre": v2.PreIT_DiffFlow_mL_min,
                      "pup": v2.PUPSIT_DiffFlow_mL_min, "attempts": v2.PreIT_Attempts})])
    u["cart"] = "FITC-" + u.cart_raw.str.extract(r"([ABC][12])$")[0]
    u["start"] = pd.to_datetime(u.start.str.replace("T", " "), utc=True)
    for c in ("pre", "pup", "attempts"):
        u[c] = pd.to_numeric(u[c].replace("-", np.nan))
    u = u[u.attempts > 0].drop_duplicates(subset=["cart", "start"])
    return u.sort_values("start")


def slope(df: pd.DataFrame, cart: str, lo, hi, col: str = "pup"):
    sub = df[(df.cart == cart) & (df.start >= lo) & (df.start < hi)].dropna(subset=[col])
    r = stats.linregress(np.arange(len(sub)), sub[col])
    return r.slope, r.pvalue


# ---------------------------------------------------------------- delivery realism
def test_daily_drops_and_manifests(data):
    drops = sorted((data / "raw/drops").iterdir())
    assert len(drops) >= C.DAYS
    m = json.loads((drops[200] / "manifest.json").read_text())
    for rel, n in m["files"].items():
        assert len(pd.read_csv(drops[200] / rel)) == n


def test_upserts_present(data):
    mes = read_system(data, "mes/batches.csv")
    states = mes.groupby("batch_id").status.apply(set)
    assert (states.apply(lambda s: {"IN_PROGRESS", "COMPLETED"} <= s)).mean() > 0.9
    wo = read_system(data, "cmms/work_orders.csv")
    assert wo.groupby("wonum").status.nunique().max() == 2
    q = read_system(data, "qms/deviations.csv")
    assert {"Open", "Closed"} <= set(q.status) and (q[q.status == "Closed"].root_cause != "").all()


def test_schema_change(data):
    s = read_system(data, "historian/assembly_summary.csv")
    change = f"{at(C.SCHEMA_CHANGE_DAY):%Y-%m-%d}"
    assert (s[s._drop < change].get("Cart", pd.Series(dtype=str)) != "").all()
    assert "Equipment" in s and (s[s._drop >= change].Equipment != "").all()
    sig_old = pd.read_csv(sorted((data / "raw/drops").glob("2025-01-*/historian/test_signals.csv"))[0])
    sig_new = pd.read_csv(sorted((data / "raw/drops").glob("2026-01-*/historian/test_signals.csv"))[0])
    assert sig_old.tag.str.startswith("FITC_").all() and sig_new.tag.str.startswith("PLT1.").all()
    wo = read_system(data, "cmms/work_orders.csv")
    cut = f"{at(C.CMMS_FAILURECODE_DAY):%Y-%m-%d}"
    assert wo[wo._drop < cut].failurecode.isna().all()  # column did not exist yet
    assert wo[wo._drop >= cut].failurecode.notna().all()


def test_outage_backfill_and_late_rows(data):
    raw = read_system(data, "historian/assembly_summary.csv")
    cart = raw.get("Cart", "").fillna("") + raw.get("Equipment", "").fillna("")
    raw["line"] = cart.str.extract(r"([ABC])[12]$")[0]
    lo, hi = C.HISTORIAN_OUTAGE
    outage = [f"{at(d):%Y-%m-%d}" for d in range(lo, hi)]
    assert not ((raw.line == "A") & raw._drop.isin(outage)).any(), "line A silent during outage"
    backfill = raw[(raw.line == "A") & (raw._drop == f"{at(hi + 1):%Y-%m-%d}")]
    assert len(backfill) >= 3, "outage rows arrive later as a backfill"
    assert raw.duplicated(subset=[c for c in raw.columns if c not in ("_drop", "line")]).any(), "resends expected"


def test_erp_reversals_balance(data):
    m = read_system(data, "erp/material_movements.csv")
    rev = m[m.movement_type == "262"]
    assert len(rev) > 10
    key = ["batch_id", "vendor_lot"]
    issued = m[m.movement_type == "261"].groupby(key).size()
    assert all(issued.get(tuple(k), 0) >= 1 for k in rev[key].values)


# ---------------------------------------------------------------- integrity / isolation
def test_ids_join_and_label_isolation(data):
    mes = read_system(data, "mes/batches.csv")
    m = read_system(data, "erp/material_movements.csv")
    assert set(m.batch_id) <= set(mes.batch_id)
    for f in list((data / "raw/drops").glob("*/*/*.csv"))[::25]:
        head = f.read_text()[:20000]
        assert "scenario" not in head.lower() and not re.search(r"\bS\d+_|RH1_", head), f


def test_distributions_not_normal(data):
    s = summary(data)
    clean = s[(s.cart == "FITC-B1") & (s.start < at(C.SCENARIOS["S4_autoclave_overtemp"]["start_day"]))]
    assert stats.skew(clean.pup.dropna()) > 0.3


def test_signals_compressed_irregular(data):
    f = sorted((data / "raw/drops").glob("2025-02-1*/historian/test_signals.csv"))[0]
    s = pd.read_csv(f, parse_dates=["timestamp"])
    one = s[s.tag.str.endswith("Pressure")].groupby("tag").timestamp.apply(lambda x: x.diff().dt.total_seconds())
    assert one.dropna().nunique() > 3, "deadband compression should give irregular spacing"


# ---------------------------------------------------------------- detectability
def test_seal_wear_drifts_detectable(data):
    s = summary(data)
    for scen in ("S1_cart_seal_wear", "S10_seal_wear_recurrence"):
        sc = C.SCENARIOS[scen]
        b, p = slope(s, sc["entity"], at(sc["start_day"]), at(sc["fix_day"]))
        assert b > 0.03 and p < 0.01, scen


def test_sensor_drift_detectable(data):
    sc = C.SCENARIOS["S5_sensor_drift"]
    b, p = slope(summary(data), sc["entity"], at(sc["start_day"]), at(sc["fix_day"]))
    assert b < 0 and p < 0.01


def test_bad_lot_elevates_pupsit(data):
    truth = pd.read_csv(data / "eval/assembly_truth.csv")
    truth["start"] = pd.to_datetime(truth.build_start, utc=True)
    df = summary(data).merge(truth[["cart_id", "start", "filter_lot"]], left_on=["cart", "start"],
                             right_on=["cart_id", "start"])
    lot = C.SCENARIOS["S2_bad_filter_lot"]["entity"]
    assert df[df.filter_lot == lot].pup.mean() - df[df.filter_lot != lot].pup.mean() > 0.6


def test_autoclave_overtemp_visible(data):
    c = read_system(data, "autoclave/cycles.csv")
    c["t"] = pd.to_datetime(c.cycle_start)
    c["temp"] = c.max_chamber_temp_c.astype(float)
    sc = C.SCENARIOS["S4_autoclave_overtemp"]
    hot = c[(c.autoclave_id == "AC-02") & (c.t >= at(sc["start_day"])) & (c.t < at(sc["fix_day"]))]
    assert len(hot) > 3 and (hot.temp > 126).all()
    assert (c[c.autoclave_id == "AC-01"].temp < 125).all()


def test_wetting_crew_effect_detectable(data):
    sc = C.SCENARIOS["S3_incomplete_wetting"]
    mes = read_system(data, "mes/batches.csv")
    mes = mes[(mes.status == "COMPLETED") & (mes.line == "LINE-C")].copy()
    mes["bs"], mes["be"] = pd.to_datetime(mes.batch_start), pd.to_datetime(mes.batch_end)
    s = summary(data)
    s = s[s.cart.str.startswith("FITC-C") & (s.start >= at(sc["start_day"])) & (s.start < at(sc["end_day"]))]
    crews = []
    for t in s.start:
        hit = mes[(mes.bs <= t) & (mes.be >= t)]
        crews.append(hit.shift_crew.iloc[0] if len(hit) else None)
    s["crew"] = crews
    s = s.dropna(subset=["crew"])
    retry = s.assign(r=s.attempts > 1).groupby(s.crew == sc["crew"]).r.mean()
    assert retry[True] > retry[False] + 0.1


def test_station_scenarios_visible(data):
    f = read_system(data, "line/filling_checks.csv")
    f = f[f.fill_weight_mg != ""]
    f["t"], f["w"], f["needle"] = pd.to_datetime(f.check_time), f.fill_weight_mg.astype(float), f.needle.astype(int)
    hi = at(C.SCENARIOS["S8_filler_needle_underfill"]["fix_day"])
    late = f[(f.line == "B") & (f.t >= hi - 4 * DAY) & (f.t < hi)]
    assert late[late.needle != 7].w.mean() - late[late.needle == 7].w.mean() > 15
    v = read_system(data, "line/stoppering_checks.csv")
    v["t"], v["vac"] = pd.to_datetime(v.check_time), v.vacuum_mbar_abs.astype(float)
    hi = at(C.SCENARIOS["S9_vacuum_pump_degradation"]["fix_day"])
    assert v[(v.line == "A") & (v.t >= hi - 3 * DAY) & (v.t < hi)].vac.mean() > 140
    ty = read_system(data, "line/tyvek_removal_alarms.csv")
    ty["t"] = pd.to_datetime(ty.alarm_time)
    hi = at(C.SCENARIOS["S7_tyvek_gripper_wear"]["fix_day"])
    a = ty[ty.line == "A"]
    assert len(a[(a.t >= hi - 4 * DAY) & (a.t < hi)]) > 5 * len(a[(a.t >= hi + 4 * DAY) & (a.t < hi + 8 * DAY)])


def test_past_case_available_for_recurrence(data):
    """The S1 deviation is closed (with root cause) before S10 starts: memory of past cases is possible."""
    q = read_system(data, "qms/deviations.csv")
    closed = q[(q.status == "Closed") & q.root_cause.str.contains("inlet seal")]
    assert (pd.to_datetime(closed.closed_at) < at(C.SCENARIOS["S10_seal_wear_recurrence"]["start_day"])).any()
