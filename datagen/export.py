"""Export layer: turn the clean truth into messy DAILY DROPS per source system.

Layout:  data/raw/drops/YYYY-MM-DD/<system>/<file>.csv  (+ manifest.json)

Each system delivers what it would really deliver on that day, with its own
conventions and flaws: aliases, units, local time zones, late rows, resends,
upserts (same record delivered again with new status), ERP reversals, an
outage with backfill, and a schema change mid-way. Ground truth goes only to
data/eval/.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .simulate import day_of

IST = pd.Timedelta(hours=5, minutes=30)
END = pd.Timestamp(C.START + dt.timedelta(days=C.DAYS))
SCHEMA_DAY = pd.Timestamp(C.START + dt.timedelta(days=C.SCHEMA_CHANGE_DAY)).normalize()
FCODE_DAY = pd.Timestamp(C.START + dt.timedelta(days=C.CMMS_FAILURECODE_DAY)).normalize()


def iso(t) -> str:
    return pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M:%SZ")


def drop_day(t) -> pd.Timestamp:
    return pd.Timestamp(t).normalize()


class Exporter:
    def __init__(self, frames: dict[str, pd.DataFrame], out: Path, seed: int = C.SEED):
        self.f = frames
        self.f["assemblies"] = frames["assemblies"].drop(columns="_true").rename(
            columns={"_pupsit_end": "pupsit_end", "_pre_end": "pre_end"})
        self.out = out
        self.rng = np.random.default_rng(seed + 1)
        self.manifest: dict[str, dict] = {}

    # ------------------------------------------------------------ writing
    def write_drops(self, df: pd.DataFrame, rel: str, day_col: str = "_drop") -> None:
        """Write one file per drop day. Columns starting with '_' are internal and dropped."""
        df = df[df[day_col] < END.normalize() + pd.Timedelta(days=1)]
        for day, part in df.groupby(day_col):
            folder = f"{pd.Timestamp(day):%Y-%m-%d}"
            out = part[[c for c in part.columns if not c.startswith("_")]]
            out = out.dropna(axis=1, how="all") if "_keep_cols" not in part else out
            p = self.out / "raw/drops" / folder / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            out.to_csv(p, index=False)
            self.manifest.setdefault(folder, {})[rel] = len(out)

    def write_manifests(self) -> None:
        for folder, files in self.manifest.items():
            p = self.out / "raw/drops" / folder / "manifest.json"
            p.write_text(json.dumps({"drop_date": folder, "files": files}, indent=1))

    def path(self, rel: str) -> Path:
        p = self.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # ------------------------------------------------------------ reference
    def equipment_master(self) -> None:
        rows = []
        for cart in C.CARTS:
            line, n = cart[5], cart[6]
            rows.append({"equipment_id": cart, "equipment_type": "filter_integrity_test_cart",
                         "line": f"LINE-{line}", "role": C.CART_ROLES[n],
                         "historian_tag_prefix_v1": f"FITC_{line}{n}", "historian_tag_prefix_v2": f"PLT1.L{line}.FITC{n}",
                         "cmms_location": f"PLT1-L{line}-FITC{n}", "commissioned": "2023-03-01"})
        for ac in ["AC-01", "AC-02"]:
            rows.append({"equipment_id": ac, "equipment_type": "autoclave", "line": "SHARED", "role": "sterilization",
                         "historian_tag_prefix_v1": ac.replace("-", "_"), "historian_tag_prefix_v2": f"PLT1.UTIL.{ac.replace('-', '')}",
                         "cmms_location": f"PLT1-UTIL-{ac.replace('-', '')}", "commissioned": "2021-08-15"})
        for line in C.LINES:
            for eq, typ in [("TRR", "tyvek_removal_robot"), ("FILLER", "rotary_filler"), ("VAC", "stopper_vacuum_pump")]:
                rows.append({"equipment_id": f"{eq}-{line}", "equipment_type": typ, "line": f"LINE-{line}", "role": typ,
                             "historian_tag_prefix_v1": f"{eq}_{line}", "historian_tag_prefix_v2": f"PLT1.L{line}.{eq}",
                             "cmms_location": f"PLT1-L{line}-{eq}", "commissioned": "2023-03-01"})
        df = pd.DataFrame(rows)
        df.to_csv(self.path("reference/equipment_master.csv"), index=False)
        self.eq = df.set_index("equipment_id")
        lines = ["# Fictional specification limits (not real values)"] + [f"{k}: {v}" for k, v in C.SPEC.items()]
        self.path("reference/spec_limits.yaml").write_text("\n".join(lines) + "\n")

    def alias(self, cart: str) -> str:
        line, n = cart[5], cart[6]
        return str(self.rng.choice([f"{line}{n}", f"FITC_{line}{n}", f"Cart {line}{n}", f"FITC-{line}{n}"],
                                   p=[0.55, 0.25, 0.1, 0.1]))

    def outage_remap(self, d: pd.Timestamp, line: str | None) -> pd.Timestamp:
        lo, hi = (drop_day(C.START + dt.timedelta(days=x)) for x in C.HISTORIAN_OUTAGE)
        if line == "A" and lo <= d < hi:
            return hi + pd.Timedelta(days=1)  # backfill after the outage
        return d

    def delivery_day(self, t, line: str | None = None, historian: bool = False) -> pd.Timestamp:
        d = drop_day(t)
        if historian:
            if self.rng.random() < C.HISTORIAN_LATE_RATE:
                d = d + pd.Timedelta(days=int(self.rng.integers(1, 4)))
            d = self.outage_remap(d, line)
        return d

    # ------------------------------------------------------------ MES (upserts)
    def batches(self) -> None:
        b, a = self.f["batches"], self.f["assemblies"]
        first = a.groupby("batch_id")["build_start"].min()
        last_ready = a.groupby("batch_id")["pupsit_end"].max()
        rows, truth = [], []
        for r in b.itertuples():
            fb, lr = first[r.batch_id], last_ready[r.batch_id]
            u = self.rng.random()
            if u < 0.85:
                rec_start, case = fb - pd.Timedelta(minutes=float(self.rng.uniform(5, 40))), "start_inside"
            elif u < 0.93:
                span = (lr - fb).total_seconds() / 3600
                rec_start, case = fb + pd.Timedelta(hours=float(self.rng.uniform(1.0, max(span - 0.5, 1.1)))), "end_inside"
            else:
                rec_start, case = lr + pd.Timedelta(minutes=float(self.rng.uniform(10, 60))), "in_gap"
            rec_end = pd.Timestamp(r.process_end) + pd.Timedelta(minutes=float(self.rng.uniform(5, 30)))
            base = {"batch_id": r.batch_id, "line": f"LINE-{r.line}", "product": r.product,
                    "recipe": f"RCP-{r.product[4:]}-v{1 + int(day_of(r.process_start) > 400)}",
                    "shift_crew": r.crew, "batch_start": iso(rec_start)}
            rows.append({**base, "batch_end": "", "status": "IN_PROGRESS", "tubs_processed": "", "total_good": "",
                         "rejects": "", "comment": "", "record_updated_at": iso(rec_start), "_drop": drop_day(rec_start)})
            rows.append({**base, "batch_end": iso(rec_end), "status": r.status, "tubs_processed": r.tubs,
                         "total_good": r.total_good, "rejects": r.rejects, "comment": r.comment,
                         "record_updated_at": iso(rec_end), "_drop": drop_day(rec_end)})
            truth.append({"batch_id": r.batch_id, "recorded_start_case": case})
        for day, bid, status in [(40, "B000000", "TEST"), (500, "B000001", "TEST"), (610, "NA-PENDING", "")]:
            t = pd.Timestamp(C.START + dt.timedelta(days=day, hours=2))
            rows.append({"batch_id": bid, "line": "LINE-B", "product": "TEST" if status else "", "recipe": "",
                         "shift_crew": "", "batch_start": iso(t), "batch_end": "", "status": status,
                         "tubs_processed": 0 if status else "", "total_good": 0 if status else "", "rejects": "",
                         "comment": "", "record_updated_at": iso(t), "_drop": drop_day(t)})
        df = pd.DataFrame(rows)
        df["_keep_cols"] = 1
        self.write_drops(df, "mes/batches.csv")
        self.batch_case = pd.DataFrame(truth)

    # ------------------------------------------------------------ historian
    def assembly_summary(self) -> None:
        a = self.f["assemblies"]
        att = self.f["attempts"]
        first_wet = att[att.test_type == "pre_it"].sort_values("attempt").groupby("assembly_id")["wetting_time_s"].first()

        def dash(v):
            if v is None or (isinstance(v, float) and np.isnan(v)) or self.rng.random() < C.MISSING_DASH_RATE:
                return "-"
            return v

        rows = []
        for r in a.itertuples():
            d = self.delivery_day(r.pupsit_end, r.line, historian=True)
            rows.append({"start": r.build_start, "end": r.pupsit_end, "cart": r.cart_id, "pre": dash(r.pre_it_flow),
                         "pup": dash(r.pupsit_flow), "wet": first_wet.get(r.assembly_id, np.nan),
                         "n_pre": int(r.pre_it_attempts), "n_pup": int(r.pupsit_attempts), "_drop": d})
            if self.rng.random() < C.HISTORIAN_RESEND_RATE:
                rows.append({**rows[-1], "_drop": self.outage_remap(d + pd.Timedelta(days=1), r.line)})
        for _ in range(int(len(a) * C.EMPTY_ASSEMBLY_ROWS)):
            t = pd.Timestamp(C.START + dt.timedelta(days=float(self.rng.uniform(0, C.DAYS))))
            line = str(self.rng.choice(C.LINES))
            rows.append({"start": t, "end": t + pd.Timedelta(minutes=12), "cart": f"FITC-{line}{self.rng.integers(1, 3)}",
                         "pre": "-", "pup": "-", "wet": np.nan, "n_pre": 0, "n_pup": 0,
                         "_drop": self.outage_remap(drop_day(t), line)})
        df = pd.DataFrame(rows)
        v1, v2 = df[df._drop < SCHEMA_DAY], df[df._drop >= SCHEMA_DAY]
        out1 = pd.DataFrame({
            "FIT_Cycle_Window": [f"{pd.Timestamp(s):%Y-%m-%d %H:%M:%S} - {pd.Timestamp(e):%Y-%m-%d %H:%M:%S}"
                                 for s, e in zip(v1.start, v1.end)],
            "Cart": [self.alias(c) for c in v1.cart], "PreIT_Flow": v1.pre.values, "PUPSIT_Flow": v1.pup.values,
            "Wetting_Time": [f"{w:.0f} s" if not np.isnan(w) else "-" for w in v1.wet],
            "Attempts": v1.n_pre.values, "PUPSIT_Attempts": v1.n_pup.values, "_drop": v1._drop.values})
        out2 = pd.DataFrame({  # after the historian software upgrade
            "Cycle_Start_UTC": [iso(s) for s in v2.start], "Cycle_End_UTC": [iso(e) for e in v2.end],
            "Equipment": [self.alias(c) for c in v2.cart], "PreIT_DiffFlow_mL_min": v2.pre.values,
            "PUPSIT_DiffFlow_mL_min": v2.pup.values,
            "Wetting_Time_s": [round(w) if not np.isnan(w) else "" for w in v2.wet],
            "PreIT_Attempts": v2.n_pre.values, "PUPSIT_Attempts": v2.n_pup.values, "_drop": v2._drop.values})
        for out in (out1, out2):
            out["_keep_cols"] = 1
            out = out.sample(frac=1, random_state=7)
            self.write_drops(out, "historian/assembly_summary.csv")
        # post-use tests arrive separately, after the batch
        pu = a.dropna(subset=["post_use_result"]) if "post_use_result" in a else a.iloc[0:0]
        pdf = pd.DataFrame({"Test_End_UTC": [iso(t) for t in pu.post_use_end],
                            "Equipment": [self.alias(c) for c in pu.cart_id],
                            "PostUse_DiffFlow_mL_min": pu.post_use_flow.values,
                            "Attempts": pu.post_use_attempts.astype(int).values,
                            "_drop": [self.delivery_day(t, l, True) for t, l in zip(pu.post_use_end, pu.line)]})
        self.write_drops(pdf, "historian/post_use_tests.csv")

    def tag(self, cart: str, kind: str, when) -> str:
        line, n = cart[5], cart[6]
        if pd.Timestamp(when) < SCHEMA_DAY:
            return f"FITC_{line}{n}." + {"step": "StepIndex", "p": "Pressure", "f": "DiffFlow"}[kind]
        return f"PLT1.L{line}.FITC{n}." + {"step": "STEP", "p": "PRES_MBAR", "f": "FLOW_MLMIN"}[kind]

    def test_signals(self) -> None:
        """Long-format historian data, stored only on change (deadband compression)."""
        att = self.f["attempts"]
        seq = [(0, 10), (100, 6), (200, 10), (300, 20), (400, 10), (500, 20), (600, 10),
               (1200, 60), (1300, 10), (1400, 12), (1500, 6), (0, 10)]
        abort = [(0, 10), (100, 6), (200, 10), (300, 20), (9999, 10), (0, 10)]
        target = C.SPEC["test_pressure_mbar"]
        chunks = []
        for r in att.itertuples():
            steps = abort if r.faulted else seq
            step = np.concatenate([np.full(d, s) for s, d in steps])
            n = len(step)
            sec = np.arange(n)
            pos = np.concatenate([np.linspace(0, 1, d, endpoint=False) for _, d in steps])
            p = np.zeros(n)
            f = np.zeros(n)
            ramp = {200: (0, .25), 300: (.25, .85), 400: (.85, 1.0)}
            for s, (lo, hi) in ramp.items():
                m = step == s
                p[m] = target * (lo + (hi - lo) * pos[m])
                f[m] = 20 - 12 * (lo + (hi - lo) * pos[m])
            hold = np.isin(step, [500, 600, 1200, 1300])
            leak_rate = 0.8 * max(r.true_flow - 1.0, 0) if r.leak else 0
            p[hold] = target - leak_rate * (sec[hold] - 56)
            f[step == 500] = 8 - 5 * pos[step == 500]
            f[step == 600] = 3 - (3 - r.true_flow) * pos[step == 600]
            m1200 = step == 1200
            f[m1200] = r.true_flow + (1.2 * np.exp(-3 * pos[m1200]) if r.reason == "incomplete_wetting" else 0)
            f[step == 1300] = r.reported_flow / r.pressure_factor if r.pressure_factor else r.true_flow
            rel = step == 1400
            if rel.any():
                p[rel] = p[np.argmax(rel) - 1] * (1 - pos[rel])
            ab = step == 9999
            if ab.any():
                p[ab] = p[np.argmax(ab) - 1] * 0.5
            p = np.clip(p + self.rng.normal(0, 3, n), 0, None) * (1 + (r.pressure_factor - 1) * 0.5)
            f = np.where(f > 0, np.clip(f + self.rng.normal(0, 0.02, n), 0, None), 0) * r.pressure_factor
            t = pd.Timestamp(r.start) + pd.to_timedelta(sec, unit="s")
            for kind, vals, band in (("step", step, 0.5), ("p", p, 8.0), ("f", f, 0.03)):
                q = np.round(vals / band)
                keep = np.r_[True, q[1:] != q[:-1]]
                keep[-1] = True
                if kind != "step":
                    keep |= np.r_[True, step[1:] != step[:-1]]  # store on step change too
                chunks.append(pd.DataFrame({"timestamp": t[keep], "tag": self.tag(r.cart_id, kind, r.start),
                                            "value": np.round(vals[keep], 3), "_line": r.line}))
        df = pd.concat(chunks, ignore_index=True)
        df["quality"] = np.where(self.rng.random(len(df)) < 0.002, "Questionable", "Good")
        lo, hi = (drop_day(C.START + dt.timedelta(days=x)) for x in C.HISTORIAN_OUTAGE)
        d = df.timestamp.dt.normalize()
        df["_drop"] = np.where((df._line == "A") & (d >= lo) & (d < hi), hi + pd.Timedelta(days=1), d)
        df["timestamp"] = df.timestamp.dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        self.write_drops(df.sort_values(["tag", "timestamp"]), "historian/test_signals.csv")

    def cart_alarms(self) -> None:
        c = self.f["cart_alarms"].copy()
        noise = []
        for _ in range(int(C.DAYS * 0.8)):  # nuisance alarms
            noise.append({"alarm_time": C.START + dt.timedelta(days=float(self.rng.uniform(0, C.DAYS))),
                          "cart_id": str(self.rng.choice(C.CARTS)), "alarm_code": "A-101",
                          "alarm_text": "Low supply air pressure (transient)"})
        c = pd.concat([c, pd.DataFrame(noise)], ignore_index=True).sort_values("alarm_time")
        c["_drop"] = c.alarm_time.map(drop_day)
        c["alarm_time"] = c.alarm_time.map(iso)
        c["equipment"] = [self.alias(x) for x in c.cart_id]
        self.write_drops(c[["alarm_time", "equipment", "alarm_code", "alarm_text", "_drop"]], "historian/cart_alarms.csv")

    # ------------------------------------------------------------ other systems
    def autoclave(self) -> None:
        c = self.f["autoclave_cycles"]
        df = pd.DataFrame({"autoclave_id": c.autoclave_id, "cycle_id": c.cycle_id, "cycle_start": c.start.map(iso),
                           "cycle_end": c.end.map(iso), "max_chamber_temp_c": c.max_temp_c,
                           "hold_time_min": c.hold_minutes,
                           "load_description": [f"Line {l} filter assemblies x{n}" if self.rng.random() > 0.2 else ""
                                                for l, n in zip(c.line, c.loads)],
                           "cycle_result": "COMPLETE", "_drop": c.end.map(drop_day)})
        df["_keep_cols"] = 1
        self.write_drops(df, "autoclave/cycles.csv")

    def incoming_inspection(self) -> None:
        lots = self.f["filter_lots"]
        df = pd.DataFrame({"inspection_id": [f"QCI-{i + 3000}" for i in range(len(lots))], "material_code": "FLT-CAP-0.2PES",
                           "vendor_code": lots.vendor, "vendor_lot": lots.lot,
                           "received_date": [(pd.Timestamp(t) + IST).strftime("%Y-%m-%d") for t in lots.received],
                           "coa_bubble_point_bar": lots.coa_bubble_point_bar, "coa_integrity_result": lots.coa_result,
                           "visual_inspection": lots.visual_inspection, "disposition": lots.status,
                           "_drop": [drop_day(t) + pd.Timedelta(days=1) for t in lots.received]})
        df = df[df._drop >= drop_day(C.START)]
        self.write_drops(df, "qc/incoming_inspection.csv")

    def materials(self) -> None:
        fu, b = self.f["filter_usage"], self.f["batches"]
        lots_by_vendor = self.f["filter_lots"].groupby("vendor")["lot"].apply(list).to_dict()
        rows, po, doc = [], 5100000, 4900000000
        for r in b.itertuples():
            po += int(self.rng.integers(1, 9))
            step = "Aseptic Filling - Main Isolator" if self.rng.random() < 0.8 else f"Main Isolator & Filler - Line {r.line}"
            post = pd.Timestamp(r.process_start) + IST + pd.Timedelta(days=1)
            d = int(day_of(r.process_start) // 15)

            def mv(mat, text, vcode, vname, lot, mtype="261", qty=1, when=post):
                nonlocal doc
                doc += int(self.rng.integers(1, 5))
                rows.append({"document_no": doc, "process_order": po, "batch_id": r.batch_id, "material_code": mat,
                             "material_text": text, "movement_type": mtype, "quantity": qty, "vendor_code": vcode,
                             "vendor_name": vname, "vendor_lot": lot, "step_text": step,
                             "posting_date": when.strftime("%Y-%m-%d"), "_drop": drop_day(when - IST)})

            mv("SYR-1ML-NEST160", "Syringe 1 mL long, nested 160/tub", "V-SYR-01", "Vitra Glass (fictional)",
               f"SY-{d:03d}{r.line}", qty=r.tubs)
            mv("STP-PLG-01", "Plunger stopper, coated", "V-STP-01", "Elasto Seal (fictional)", f"ST-{d:03d}",
               qty=r.tubs * C.SYRINGES_PER_TUB)
            for u in fu[fu.batch_id == r.batch_id].itertuples():
                name = C.FILTER_VENDORS[u.vendor]["name"]
                lot = u.lot if self.rng.random() > C.VENDOR_LOT_BLANK_RATE else ""
                text = "Filter capsule 0.2 um PES sterilizing grade"
                if lot and self.rng.random() < C.ERP_CORRECTION_RATE:
                    wrong = str(self.rng.choice([x for x in lots_by_vendor[u.vendor] if x != u.lot] or [u.lot]))
                    mv("FLT-CAP-0.2PES", text, u.vendor, name, wrong)
                    later = post + pd.Timedelta(days=int(self.rng.integers(1, 3)))
                    mv("FLT-CAP-0.2PES", text, u.vendor, name, wrong, "262", -1, later)  # reversal
                    mv("FLT-CAP-0.2PES", text, u.vendor, name, lot, "261", 1, later)    # correct re-post
                else:
                    mv("FLT-CAP-0.2PES", text, u.vendor, name, lot)
        df = pd.DataFrame(rows)
        df["_keep_cols"] = 1
        self.write_drops(df, "erp/material_movements.csv")

    def work_orders(self) -> None:
        w = self.f["work_orders"].sort_values("created")
        rows = []
        legacy_until = pd.Timestamp(C.START + dt.timedelta(days=300))
        for r in w.itertuples():
            loc = self.eq.loc[r.equipment, "cmms_location"]
            if r.equipment.startswith("FITC") and pd.Timestamp(r.created) < legacy_until:
                loc = loc.replace("FITC", "FITC-0")
            fmt = "%Y-%m-%d %H:%M:%S" if self.rng.random() < 0.7 else "%d/%m/%Y %I:%M %p"
            lc, lf = pd.Timestamp(r.created) + IST, pd.Timestamp(r.actual_finish) + IST
            wtype = r.work_type if not (r.work_type == "CM" and self.rng.random() < 0.15) else "SA"
            base = {"wonum": r.wo_number, "location": loc, "worktype": wtype, "createdate": lc.strftime(fmt),
                    "description": r.description, "siteid": "PLT1"}
            rows.append({**base, "status": "WAPPR", "actfinish": "", "statusdate": lc.strftime(fmt),
                         "longdescription": "", "failurecode": "", "_drop": drop_day(r.created)})
            sd = lf.strftime(fmt) if self.rng.random() > 0.03 else lf.strftime("%M:%S.0")
            rows.append({**base, "status": "COMP", "actfinish": lf.strftime(fmt), "statusdate": sd,
                         "longdescription": f"<div><p>{r.long_description}</p></div>",
                         "failurecode": r.failure_code, "_drop": drop_day(r.actual_finish)})
        df = pd.DataFrame(rows)
        old, new = df[df._drop < FCODE_DAY].drop(columns="failurecode"), df[df._drop >= FCODE_DAY]
        for part in (old, new):
            part = part.copy()
            part["_keep_cols"] = 1
            self.write_drops(part, "cmms/work_orders.csv")

    def deviations(self) -> None:
        d = self.f["deviations"].sort_values("opened_at").reset_index(drop=True)
        rows = []
        for i, r in d.iterrows():
            base = {"deviation_id": f"DEV-{pd.Timestamp(r.opened_at):%Y}-{100 + i:04d}", "opened_at": iso(r.opened_at),
                    "line": f"LINE-{r.line}", "batch_id": r.batch_id if self.rng.random() > 0.2 else "",
                    "equipment": self.alias(r.cart_id) if self.rng.random() > 0.3 else "", "category": r.category,
                    "short_description": f"{r.failed_test} failed all attempts on filter assembly",
                    "initial_assessment": r.initial_assessment}
            rows.append({**base, "status": "Open", "root_cause": "", "closed_at": "", "record_updated_at": iso(r.published_at),
                         "_drop": drop_day(r.published_at)})
            rows.append({**base, "status": "Closed", "root_cause": r.root_cause, "closed_at": iso(r.closed_at),
                         "record_updated_at": iso(r.closed_at), "_drop": drop_day(r.closed_at)})
        df = pd.DataFrame(rows)
        df["_keep_cols"] = 1
        self.write_drops(df, "qms/deviations.csv")

    def stations(self) -> None:
        ty = self.f["tyvek_alarms"].drop(columns="scenario_tags").sort_values("alarm_time")
        ty["_drop"] = ty.alarm_time.map(drop_day)
        ty["alarm_time"] = ty.alarm_time.map(iso)
        self.write_drops(ty, "line/tyvek_removal_alarms.csv")
        fc = self.f["filling_checks"].drop(columns="scenario_tags")
        fc["_drop"] = fc.check_time.dt.normalize()
        fc["check_time"] = fc.check_time.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        fc["fill_weight_mg"] = fc.fill_weight_mg.astype(object)
        fc.loc[self.rng.random(len(fc)) < 0.005, "fill_weight_mg"] = ""
        fc["_keep_cols"] = 1
        self.write_drops(fc, "line/filling_checks.csv")
        st = self.f["stopper_checks"].drop(columns="scenario_tags")
        st["_drop"] = st.check_time.dt.normalize()
        st["check_time"] = st.check_time.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.write_drops(st, "line/stoppering_checks.csv")

    def environment(self) -> None:
        e = self.f["environment"].copy()
        e = e[self.rng.random(len(e)) > 0.01]
        e["temperature"] = np.where(e.line == "C", (e.room_temp_c * 9 / 5 + 32).round(1), e.room_temp_c)
        e["temperature_unit"] = np.where(e.line == "C", "F", "C")
        e["_drop"] = e.timestamp.map(drop_day)
        e["timestamp"] = e.timestamp.map(iso)
        e["line"] = "LINE-" + e.line
        self.write_drops(e[["timestamp", "line", "temperature", "temperature_unit", "rel_humidity_pct", "_drop"]],
                         "environment/room_conditions.csv")

    # ------------------------------------------------------------ evaluation only
    def eval_labels(self) -> None:
        dev = self.f["deviations"]
        scen = {}
        for k, v in C.SCENARIOS.items():
            v = dict(v)
            for key in ("start_day", "end_day", "fix_day"):
                if key in v:
                    v[key.replace("day", "utc")] = iso(C.START + dt.timedelta(days=v[key]))
            first_dev = dev[dev.scenario_tags.str.contains(k)].opened_at.min() if len(dev) else pd.NaT
            stop = v.get("fix_day", v.get("end_day"))
            fallback = C.START + dt.timedelta(days=stop - 1)
            v["suggested_investigation_as_of_utc"] = iso(first_dev if pd.notna(first_dev) else fallback)
            scen[k] = v
        note = {"label_use": "OFFLINE EVALUATION ONLY - never load into pipelines, prompts, retrieval or features",
                "scenarios": scen}
        self.path("eval/scenario_labels.json").write_text(json.dumps(note, indent=2, default=str))
        a = self.f["assemblies"]
        out = a[["assembly_id", "cart_id", "line", "batch_id", "crew", "build_start", "filter_vendor", "filter_lot",
                 "autoclave_cycle_id", "is_replacement", "pre_it_result", "pupsit_result", "scenario_tags"]].copy()
        out["build_start"] = out.build_start.map(iso)
        out.merge(self.batch_case, on="batch_id", how="left").to_csv(self.path("eval/assembly_truth.csv"), index=False)
        att = self.f["attempts"].copy()
        att["start"] = att.start.map(iso)
        att[["assembly_id", "cart_id", "test_type", "attempt", "start", "true_flow", "reported_flow", "reason",
             "scenario_tags"]].to_csv(self.path("eval/test_attempt_truth.csv"), index=False)

    def run(self) -> None:
        self.equipment_master()
        self.batches()
        self.assembly_summary()
        self.test_signals()
        self.cart_alarms()
        self.autoclave()
        self.incoming_inspection()
        self.materials()
        self.work_orders()
        self.deviations()
        self.stations()
        self.environment()
        self.write_manifests()
        self.eval_labels()
