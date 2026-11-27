"""Export layer: turn the clean truth into messy source-system files.

Each function writes what one real system would give you, with that system's
own conventions and flaws (aliases, units, time zones, missing values, late
publication, duplicates). Ground truth goes only to data/eval/.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .simulate import day_of

IST = dt.timedelta(hours=5, minutes=30)
END = C.START + dt.timedelta(days=C.DAYS)


def iso(t) -> str:
    return pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%SZ")


class Exporter:
    def __init__(self, frames: dict[str, pd.DataFrame], out: Path, seed: int = C.SEED):
        self.f = frames
        self.out = out
        self.rng = np.random.default_rng(seed + 1)

    def path(self, rel: str) -> Path:
        p = self.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # ------------------------------------------------------------ reference
    def equipment_master(self) -> pd.DataFrame:
        rows = []
        for cart in C.CARTS:
            line, n = cart[5], cart[6]
            rows.append({"equipment_id": cart, "equipment_type": "filter_integrity_test_cart", "line": f"LINE-{line}",
                         "role": C.CART_ROLES[n], "historian_tag_prefix": f"FITC_{line}{n}",
                         "cmms_location": f"PLT1-L{line}-FITC{n}", "commissioned": "2023-03-01"})
        for ac in ["AC-01", "AC-02"]:
            rows.append({"equipment_id": ac, "equipment_type": "autoclave", "line": "SHARED", "role": "sterilization",
                         "historian_tag_prefix": ac.replace("-", "_"), "cmms_location": f"PLT1-UTIL-{ac.replace('-', '')}",
                         "commissioned": "2021-08-15"})
        for line in C.LINES:
            for eq, typ in [("TRR", "tyvek_removal_robot"), ("FILLER", "rotary_filler"), ("VAC", "stopper_vacuum_pump")]:
                rows.append({"equipment_id": f"{eq}-{line}", "equipment_type": typ, "line": f"LINE-{line}",
                             "role": typ, "historian_tag_prefix": f"{eq}_{line}",
                             "cmms_location": f"PLT1-L{line}-{eq}", "commissioned": "2023-03-01"})
        df = pd.DataFrame(rows)
        df.to_csv(self.path("reference/equipment_master.csv"), index=False)
        self.eq = df.set_index("equipment_id")
        return df

    def spec_limits(self) -> None:
        lines = ["# Fictional specification limits used by the line (not real values)"]
        lines += [f"{k}: {v}" for k, v in C.SPEC.items()]
        self.path("reference/spec_limits.yaml").write_text("\n".join(lines) + "\n")

    # ------------------------------------------------------------ MES batches
    def batches(self) -> pd.DataFrame:
        b = self.f["batches"].copy()
        a = self.f["assemblies"]
        first = a.groupby("batch_id").agg(first_build=("build_start", "min"))
        last_ready = a.groupby("batch_id")["_pupsit_end"].max()
        rows, truth = [], []
        for _, r in b.iterrows():
            fb, lr = first.loc[r.batch_id, "first_build"], last_ready.loc[r.batch_id]
            u = self.rng.random()
            if u < 0.85:
                rec_start, case = fb - dt.timedelta(minutes=float(self.rng.uniform(5, 40))), "start_inside"
            elif u < 0.93:
                span = (lr - fb).total_seconds() / 3600
                rec_start, case = fb + dt.timedelta(hours=float(self.rng.uniform(1.0, max(span - 0.5, 1.1)))), "end_inside"
            else:
                rec_start, case = lr + dt.timedelta(minutes=float(self.rng.uniform(10, 60))), "in_gap"
            rec_end = r.process_end + dt.timedelta(minutes=float(self.rng.uniform(5, 30)))
            rows.append({"batch_id": r.batch_id, "line": f"LINE-{r.line}", "product": r["product"],
                         "recipe": f"RCP-{r['product'][4:]}-v{int(self.rng.integers(1, 3))}",
                         "batch_start": iso(rec_start), "batch_end": iso(rec_end), "status": r.status,
                         "tubs_processed": r.tubs, "total_good": r.total_good, "rejects": r.rejects})
            truth.append({"batch_id": r.batch_id, "recorded_start_case": case})
        rows.append({"batch_id": "B000000", "line": "LINE-B", "product": "TEST", "recipe": "RCP-TEST",
                     "batch_start": iso(C.START + dt.timedelta(days=12, hours=2)),
                     "batch_end": iso(C.START + dt.timedelta(days=12, hours=3)), "status": "TEST",
                     "tubs_processed": 0, "total_good": 0, "rejects": 0})
        rows.append({"batch_id": "NA-PENDING", "line": "LINE-A", "product": "", "recipe": "",
                     "batch_start": iso(C.START + dt.timedelta(days=77, hours=5)), "batch_end": "",
                     "status": "", "tubs_processed": "", "total_good": "", "rejects": ""})
        df = pd.DataFrame(rows).sample(frac=1, random_state=3)
        df.to_csv(self.path("raw/mes/batches.csv"), index=False)
        self.batch_case = pd.DataFrame(truth)
        return df

    # ------------------------------------------------------------ historian
    def alias(self, cart: str) -> str:
        line, n = cart[5], cart[6]
        return str(self.rng.choice([f"{line}{n}", f"FITC_{line}{n}", f"Cart {line}{n}", f"FITC-{line}{n}"],
                                   p=[0.55, 0.25, 0.1, 0.1]))

    def assembly_summary(self) -> None:
        a = self.f["assemblies"].copy()
        att = self.f["attempts"]
        first_wet = att[att.test_type == "pre_it"].sort_values("attempt").groupby("assembly_id")["wetting_time_s"].first()

        def fmt(v):
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return "-"
            return v if self.rng.random() > C.MISSING_DASH_RATE else "-"

        rows = []
        for _, r in a.iterrows():
            rows.append({
                "FIT_Cycle_Window": f"{pd.Timestamp(r.build_start):%Y-%m-%d %H:%M:%S} - {pd.Timestamp(r._pupsit_end):%Y-%m-%d %H:%M:%S}",
                "Cart": self.alias(r.cart_id), "PreIT_Flow": fmt(r.pre_it_flow), "PUPSIT_Flow": fmt(r.pupsit_flow),
                "PostUse_Flow": fmt(r.get("post_use_flow")),
                "Wetting_Time": f"{first_wet.get(r.assembly_id):.0f} s" if r.assembly_id in first_wet else "-",
                "Attempts": int(r.pre_it_attempts), "PUPSIT_Attempts": int(r.pupsit_attempts),
                "_line": r.line, "_t": r.build_start})
        n_empty = int(len(rows) * C.EMPTY_ASSEMBLY_ROWS)
        for _ in range(n_empty):
            t = C.START + dt.timedelta(days=float(self.rng.uniform(0, C.DAYS)))
            line = str(self.rng.choice(C.LINES))
            rows.append({"FIT_Cycle_Window": f"{t:%Y-%m-%d %H:%M:%S} - {t + dt.timedelta(minutes=12):%Y-%m-%d %H:%M:%S}",
                         "Cart": self.alias(f"FITC-{line}{self.rng.integers(1, 3)}"), "PreIT_Flow": "-",
                         "PUPSIT_Flow": "-", "PostUse_Flow": "-", "Wetting_Time": "-", "Attempts": 0,
                         "PUPSIT_Attempts": 0, "_line": line, "_t": t})
        df = pd.DataFrame(rows)
        # Exports pulled at different times with overlapping windows -> duplicates, unsorted.
        windows = [(0, 50), (40, 95), (85, C.DAYS)]
        for line in C.LINES:
            sub = df[df._line == line]
            for i, (s, e) in enumerate(windows, 1):
                lo, hi = C.START + dt.timedelta(days=s), C.START + dt.timedelta(days=e)
                part = sub[(sub._t >= lo) & (sub._t < hi)].drop(columns=["_line", "_t"])
                part = part.sample(frac=1, random_state=10 * i)
                part.to_csv(self.path(f"raw/historian/assembly_summary/LINE-{line}_export_{i}.csv"), index=False)

    def test_signals(self) -> None:
        """Seeq-style time series exports per cart per month (2 s samples)."""
        att = self.f["attempts"].sort_values("start")
        steps = [(0, 10), (100, 6), (200, 10), (300, 20), (400, 10), (500, 20), (600, 10),
                 (1200, 60), (1300, 10), (1400, 12), (1500, 6), (0, 10)]
        target = C.SPEC["test_pressure_mbar"]
        per_cart: dict[str, list] = {c: [] for c in C.CARTS}
        for r in att.itertuples():
            t0 = pd.Timestamp(r.start)
            compress = self.rng.random() < 0.3  # historian compression drops the 500 marker
            seq = steps if not r.faulted else [(0, 10), (100, 6), (200, 10), (300, 20), (9999, 10), (0, 10)]
            t, p_prev = 0, 0.0
            pf = 1 + (r.pressure_factor - 1) * 0.5
            excess = max(r.true_flow - 1.0, 0)
            for step, dur in seq:
                for s in range(0, dur, 2):
                    frac = s / dur
                    if step in (200, 300, 400):
                        lvl = {200: 0.0, 300: 0.25, 400: 0.85}[step]
                        nxt = {200: 0.25, 300: 0.85, 400: 1.0}[step]
                        p = target * (lvl + (nxt - lvl) * frac)
                        flow = 20 - 12 * (lvl + (nxt - lvl) * frac)
                    elif step in (500, 600, 1200, 1300):
                        hold_t = t - 56
                        p = target - (0.8 * excess * hold_t if r.leak else 0)
                        if step == 500:
                            flow = 8 - 5 * frac
                        elif step == 600:
                            flow = 3 - (3 - r.true_flow) * frac
                        elif step == 1200:
                            flow = r.true_flow + (1.2 * np.exp(-3 * frac) if r.reason == "incomplete_wetting" else 0)
                        else:
                            flow = r.reported_flow / r.pressure_factor if r.pressure_factor else r.true_flow
                    elif step == 1400:
                        p, flow = p_prev * (1 - frac), 0.0
                    elif step == 9999:
                        p, flow = p_prev * 0.5, 0.0
                    else:
                        p, flow = 0.0, 0.0
                    if step == 500 and compress:
                        t += 2
                        p_prev = p
                        continue
                    noise_p = self.rng.normal(0, 3)
                    noise_f = self.rng.normal(0, 0.02) if flow else 0
                    per_cart[r.cart_id].append((t0 + pd.Timedelta(seconds=t), step,
                                                round(max(p + noise_p, 0) * pf, 1),
                                                round(max(flow + noise_f, 0) * r.pressure_factor, 3)))
                    p_prev = p
                    t += 2
        for cart, rows in per_cart.items():
            tag = f"FITC_{cart[5:]}"
            df = pd.DataFrame(rows, columns=["Date-Time", f"{tag} StepIndex", f"{tag} Pressure (mbar)",
                                             f"{tag} Diffusion Flow (mL/min)"])
            df["month"] = df["Date-Time"].dt.strftime("%Y-%m")
            for month, part in df.groupby("month"):
                m0 = pd.Timestamp(month + "-01")
                nxt = (m0 + pd.offsets.MonthBegin(1))
                extra = df[(df["Date-Time"] >= nxt) & (df["Date-Time"] < nxt + pd.Timedelta(days=1))]
                out = pd.concat([part, extra]).drop(columns="month")
                out["Date-Time"] = out["Date-Time"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                out.to_csv(self.path(f"raw/historian/test_signals/{tag}_{month}.csv"), index=False)

    # ------------------------------------------------------------ other systems
    def autoclave(self) -> None:
        c = self.f["autoclave_cycles"]
        rows = []
        for r in c.itertuples():
            load = f"Line {r.line} filter assemblies x{r.loads}" if self.rng.random() > 0.2 else ""
            rows.append({"autoclave_id": r.autoclave_id, "cycle_id": r.cycle_id, "cycle_start": iso(r.start),
                         "cycle_end": iso(r.end), "max_chamber_temp_c": r.max_temp_c,
                         "hold_time_min": r.hold_minutes, "load_description": load,
                         "cycle_result": "COMPLETE"})
        pd.DataFrame(rows).to_csv(self.path("raw/autoclave/cycles.csv"), index=False)

    def materials(self) -> None:
        fu = self.f["filter_usage"]
        b = self.f["batches"]
        rows, po = [], 5100000
        for r in b.itertuples():
            po += int(self.rng.integers(1, 9))
            step = "Aseptic Filling - Main Isolator" if self.rng.random() < 0.8 else f"Main Isolator & Filler - Line {r.line}"
            post = (pd.Timestamp(r.process_start) + IST).strftime("%Y-%m-%d")
            d = int(day_of(r.process_start) // 15)
            rows.append({"process_order": po, "batch_id": r.batch_id, "material_code": "SYR-1ML-NEST160",
                         "material_text": "Syringe 1 mL long, nested 160/tub", "vendor_code": "V-SYR-01",
                         "vendor_name": "Vitra Glass (fictional)", "vendor_lot": f"SY-{d:03d}{r.line}",
                         "step_text": step, "posting_date": post})
            rows.append({"process_order": po, "batch_id": r.batch_id, "material_code": "STP-PLG-01",
                         "material_text": "Plunger stopper, coated", "vendor_code": "V-STP-01",
                         "vendor_name": "Elasto Seal (fictional)", "vendor_lot": f"ST-{d:03d}",
                         "step_text": step, "posting_date": post})
            for u in fu[fu.batch_id == r.batch_id].itertuples():
                lot = u.lot if self.rng.random() > C.VENDOR_LOT_BLANK_RATE else ""
                rows.append({"process_order": po, "batch_id": r.batch_id, "material_code": "FLT-CAP-0.2PES",
                             "material_text": "Filter capsule 0.2 um PES sterilizing grade", "vendor_code": u.vendor,
                             "vendor_name": C.FILTER_VENDORS[u.vendor]["name"], "vendor_lot": lot,
                             "step_text": step, "posting_date": post})
        pd.DataFrame(rows).to_csv(self.path("raw/erp/material_consumption.csv"), index=False)

    def work_orders(self) -> None:
        w = self.f["work_orders"].sort_values("created")
        rows = []
        for r in w.itertuples():
            loc = self.eq.loc[r.equipment, "cmms_location"]
            if r.equipment.startswith("FITC") and day_of(r.created) < 45:
                loc = loc.replace("FITC", "FITC-0")  # legacy location naming
            local_c, local_f = pd.Timestamp(r.created) + IST, pd.Timestamp(r.actual_finish) + IST
            fmt = "%Y-%m-%d %H:%M:%S" if self.rng.random() < 0.7 else "%d/%m/%Y %I:%M %p"
            wtype = r.work_type if not (r.work_type == "CM" and self.rng.random() < 0.15) else "SA"
            status_date = local_f.strftime(fmt) if self.rng.random() > 0.03 else local_f.strftime("%M:%S.0")
            ld = r.long_description if r.long_description.startswith("<") else f"<div>{r.long_description}</div>"
            rows.append({"wonum": r.wo_number, "location": loc, "worktype": wtype, "createdate": local_c.strftime(fmt),
                         "actfinish": local_f.strftime(fmt), "statusdate": status_date, "description": r.description,
                         "longdescription": ld, "siteid": "PLT1"})
        pd.DataFrame(rows).to_csv(self.path("raw/cmms/work_orders.csv"), index=False)

    def stations(self) -> None:
        ty = self.f["tyvek_alarms"].drop(columns="scenario_tags").sort_values("alarm_time")
        ty["alarm_time"] = ty.alarm_time.map(iso)
        ty.to_csv(self.path("raw/line/tyvek_removal_alarms.csv"), index=False)
        fc = self.f["filling_checks"].drop(columns="scenario_tags")
        fc["check_time"] = fc.check_time.map(iso)
        miss = self.rng.random(len(fc)) < 0.005
        fc["fill_weight_mg"] = fc.fill_weight_mg.astype(object)
        fc.loc[miss, "fill_weight_mg"] = ""
        fc.to_csv(self.path("raw/line/filling_checks.csv"), index=False)
        st = self.f["stopper_checks"].drop(columns="scenario_tags")
        st["check_time"] = st.check_time.map(iso)
        st.to_csv(self.path("raw/line/stoppering_checks.csv"), index=False)

    def environment(self) -> None:
        e = self.f["environment"].copy()
        e = e[self.rng.random(len(e)) > 0.01]
        e["temperature"] = np.where(e.line == "C", (e.room_temp_c * 9 / 5 + 32).round(1), e.room_temp_c)
        e["temperature_unit"] = np.where(e.line == "C", "F", "C")
        e["timestamp"] = e.timestamp.map(iso)
        e["line"] = "LINE-" + e.line
        e[["timestamp", "line", "temperature", "temperature_unit", "rel_humidity_pct"]].to_csv(
            self.path("raw/environment/room_conditions.csv"), index=False)

    def deviations(self) -> None:
        d = self.f["deviations"].sort_values("opened_at")
        rows, n = [], 0
        for r in d.itertuples():
            if pd.Timestamp(r.published_at) > END:
                continue  # not yet published when the export was taken
            n += 1
            rows.append({"deviation_id": f"DEV-2026-{140 + n:04d}", "opened_at": iso(r.opened_at),
                         "published_at": iso(r.published_at), "line": f"LINE-{r.line}",
                         "batch_id": r.batch_id if self.rng.random() > 0.2 else "",
                         "equipment": self.alias(r.cart_id) if self.rng.random() > 0.3 else "",
                         "category": r.category,
                         "short_description": f"{r.failed_test} failed all attempts on filter assembly",
                         "initial_assessment": r.initial_assessment,
                         "status": "Open" if pd.Timestamp(r.opened_at) > END - dt.timedelta(days=20) else "Closed"})
        pd.DataFrame(rows).to_csv(self.path("raw/qms/deviations.csv"), index=False)

    # ------------------------------------------------------------ evaluation only
    def eval_labels(self) -> None:
        scen = {k: {kk: vv for kk, vv in v.items()} for k, v in C.SCENARIOS.items()}
        for v in scen.values():
            for key in ("start_day", "end_day", "fix_day", "line_c_start_day", "line_c_end_day"):
                if key in v:
                    v[key.replace("day", "utc")] = iso(C.START + dt.timedelta(days=v[key]))
        note = {"label_use": "OFFLINE EVALUATION ONLY - never load into pipelines, prompts, retrieval or features",
                "scenarios": scen}
        self.path("eval/scenario_labels.json").write_text(json.dumps(note, indent=2, default=str))
        a = self.f["assemblies"]
        cols = ["assembly_id", "cart_id", "line", "batch_id", "build_start", "filter_vendor", "filter_lot",
                "autoclave_cycle_id", "is_replacement", "pre_it_result", "pupsit_result", "scenario_tags"]
        out = a[cols].copy()
        out["build_start"] = out.build_start.map(iso)
        out = out.merge(self.batch_case, on="batch_id", how="left")
        out.to_csv(self.path("eval/assembly_truth.csv"), index=False)
        att = self.f["attempts"].copy()
        att["start"] = att.start.map(iso)
        att[["assembly_id", "cart_id", "test_type", "attempt", "start", "true_flow", "reported_flow",
             "reason", "scenario_tags"]].to_csv(self.path("eval/test_attempt_truth.csv"), index=False)

    def run(self) -> None:
        self.equipment_master()
        self.spec_limits()
        self.batches()
        self.assembly_summary()
        self.test_signals()
        self.autoclave()
        self.materials()
        self.work_orders()
        self.stations()
        self.environment()
        self.deviations()
        self.eval_labels()
