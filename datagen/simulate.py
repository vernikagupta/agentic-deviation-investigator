"""Truth simulation: what physically happened on the line.

Produces clean tables with exact timestamps and IDs. Nothing here goes to
data/raw directly; export.py turns it into messy daily drops. Keeping truth and
export separate means every messy file can be checked against a known answer.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as C


def day_of(t) -> float:
    return (pd.Timestamp(t).to_pydatetime().replace(tzinfo=None) - C.START).total_seconds() / 86400


def td(**kw) -> dt.timedelta:
    return dt.timedelta(**{k: float(v) for k, v in kw.items()})


@dataclass
class Truth:
    batches: list = field(default_factory=list)
    assemblies: list = field(default_factory=list)
    attempts: list = field(default_factory=list)
    cart_alarms: list = field(default_factory=list)
    autoclave_cycles: list = field(default_factory=list)
    filter_usage: list = field(default_factory=list)
    filter_lots: dict = field(default_factory=dict)
    work_orders: list = field(default_factory=list)
    deviations: list = field(default_factory=list)
    tyvek_alarms: list = field(default_factory=list)
    filling_frames: list = field(default_factory=list)
    stopper_frames: list = field(default_factory=list)
    environment: list = field(default_factory=list)

    def frames(self) -> dict[str, pd.DataFrame]:
        out = {k: pd.DataFrame(v) for k, v in self.__dict__.items()
               if k not in ("filling_frames", "stopper_frames", "filter_lots")}
        out["filter_lots"] = pd.DataFrame(self.filter_lots.values())
        out["filling_checks"] = pd.concat(self.filling_frames, ignore_index=True)
        out["stopper_checks"] = pd.concat(self.stopper_frames, ignore_index=True)
        return out


class Simulator:
    def __init__(self, seed: int = C.SEED):
        self.rng = np.random.default_rng(seed)
        self.t = Truth()
        self.cart_count = {c: 0 for c in C.CARTS}          # assemblies built per cart
        self.since_seal = {c: 0 for c in C.CARTS}          # assemblies since last seal replacement
        self.scenario_start_idx: dict[str, int] = {}
        self.seal_pm_day = {c: [d + self.rng.uniform(-10, 10) for d in C.SEAL_KIT_PM_DAYS] for c in C.CARTS}
        self.batch_ids = iter(self.rng.choice(np.arange(400000, 999999), 5000, replace=False))
        self.temp_cache: dict[tuple, float] = {}

    # ------------------------------------------------------------ helpers
    def active(self, scen: str, d: float) -> bool:
        s = C.SCENARIOS[scen]
        return s["start_day"] <= d < s.get("fix_day", s.get("end_day"))

    def crew(self, line: str, t: dt.datetime) -> str:
        d = day_of(t)
        night = not (6 <= t.hour < 18)
        idx = (int(d // 2) + (2 if night else 0)) % C.CREWS_PER_LINE
        return f"{line}-CREW{idx + 1}"

    def room_temp(self, line: str, t: dt.datetime) -> float:
        key = (line, t.replace(minute=0, second=0, microsecond=0))
        if key not in self.temp_cache:
            d = day_of(key[1])
            seasonal = 0.8 * np.sin(2 * np.pi * (d - 200) / 365)  # mild yearly cycle
            base = 21.0 + seasonal + 0.5 * np.sin(2 * np.pi * key[1].hour / 24)
            s6 = C.SCENARIOS["S6_warm_room"]
            if line == "A" and s6["start_day"] <= d < s6["end_day"]:
                base = self.rng.uniform(*s6["temp_c"])
            self.temp_cache[key] = round(base + self.rng.normal(0, 0.3), 2)
        return self.temp_cache[key]

    def filter_lot(self, line: str, t: dt.datetime) -> tuple[str, str]:
        d = day_of(t)
        s2, rh = C.SCENARIOS["S2_bad_filter_lot"], C.SCENARIOS["RH1_new_lot_coincidence"]
        if line in s2["lines"] and s2["start_day"] <= d < s2["end_day"] and self.rng.random() < 0.85:
            vendor, lot = s2["vendor"], s2["entity"]
        elif line in rh["lines"] and rh["start_day"] <= d < rh["end_day"] and self.rng.random() < 0.8:
            vendor, lot = rh["vendor"], rh["entity"]
        else:
            vendor = "V-FLT-01" if self.rng.random() < C.FILTER_VENDORS["V-FLT-01"]["share"] else "V-FLT-02"
            period = int(d // C.LOT_ROTATION_DAYS)
            prefix = "VL1" if vendor == "V-FLT-01" else "VL2"
            lot = f"{prefix}-{(C.START + td(days=period * C.LOT_ROTATION_DAYS)).strftime('%m%d')}"
            if period * C.LOT_ROTATION_DAYS >= 365:
                lot += "Y2"
            if lot in (s2["entity"], rh["entity"]):
                lot += "B"
        if lot not in self.t.filter_lots:
            note = "No defects observed"
            if lot == s2["entity"]:
                note = "Minor carton damage on 2 of 40 cartons; product accepted"
            elif self.rng.random() < 0.1:
                note = str(self.rng.choice(["Label slightly misaligned; accepted", "Outer box dented; contents OK"]))
            self.t.filter_lots[lot] = {
                "lot": lot, "vendor": vendor, "received": t - td(days=self.rng.uniform(5, 20)),
                "coa_bubble_point_bar": round(float(self.rng.normal(3.6, 0.08)), 2),
                "coa_result": "PASS", "visual_inspection": note, "status": "RELEASED"}
        return vendor, lot

    # ------------------------------------------------------------ integrity tests
    def true_flows(self, cart: str, t: dt.datetime, lot: str) -> dict:
        line = cart[5]
        d = day_of(t)
        pm, ps, um, us = C.BASELINE[cart]
        temp = self.room_temp(line, t)
        shared = self.rng.normal()
        pre = pm * np.exp(ps * (0.35 * shared + 0.94 * self.rng.normal()))
        pup = um * np.exp(us * (0.35 * shared + 0.94 * self.rng.normal()))
        if self.rng.random() < C.TAIL_RATE:            # right tail: non-normal behaviour
            pup += self.rng.gamma(2.0, 0.18)
            pre += self.rng.gamma(2.0, 0.04)
        pre += 0.012 * (temp - 21) + C.AGING_PER_ASSEMBLY["pre"] * self.since_seal[cart]
        pup += 0.04 * (temp - 21) + C.AGING_PER_ASSEMBLY["pup"] * self.since_seal[cart]
        tags = []
        for scen in ("S1_cart_seal_wear", "S10_seal_wear_recurrence"):
            s = C.SCENARIOS[scen]
            if cart == s["entity"] and self.active(scen, d):
                self.scenario_start_idx.setdefault(scen, self.cart_count[cart])
                k = self.cart_count[cart] - self.scenario_start_idx[scen]
                pre += s["pre_it_slope_per_assembly"] * k
                pup += s["pupsit_slope_per_assembly"] * k
                tags.append(scen)
        s2 = C.SCENARIOS["S2_bad_filter_lot"]
        if lot == s2["entity"]:
            pre += self.rng.uniform(*s2["pre_it_shift"])
            pup += self.rng.uniform(*s2["pupsit_shift"])
            tags.append("S2_bad_filter_lot")
        s6 = C.SCENARIOS["S6_warm_room"]
        if line == "A" and s6["start_day"] <= d < s6["end_day"]:
            tags.append("S6_warm_room")
        if lot == C.SCENARIOS["RH1_new_lot_coincidence"]["entity"]:
            tags.append("RH1_new_lot_coincidence")
        factor = 1.0
        s5 = C.SCENARIOS["S5_sensor_drift"]
        if cart == s5["entity"] and self.active("S5_sensor_drift", d):
            factor = 1 + s5["reported_factor_per_day"] * (d - s5["start_day"])
            tags.append("S5_sensor_drift")
        return {"pre": max(pre, 0.2), "pup": max(pup, 1.0), "post": pup + self.rng.uniform(0.05, 0.35),
                "factor": factor, "temp": temp, "tags": tags}

    def alarm(self, cart: str, t: dt.datetime, code: str, text: str) -> None:
        self.t.cart_alarms.append({"alarm_time": t, "cart_id": cart, "alarm_code": code, "alarm_text": text})

    def run_test(self, a: dict, test_type: str, start: dt.datetime, true_value: float, limit: float,
                 wetting_s: float | None) -> tuple[dt.datetime, str, int, float]:
        cart, factor, tags = a["cart_id"], a["_true"]["factor"], a["_true"]["tags"]
        t, attempt, wet = start, 0, wetting_s
        leak = any(s in tags for s in ("S1_cart_seal_wear", "S10_seal_wear_recurrence"))
        while True:
            attempt += 1
            reason = "normal"
            value = true_value * np.exp(self.rng.normal(0, 0.01))
            if attempt == 1 and wet is not None and wet < C.SPEC["wetting_min_s"]:
                value = true_value + self.rng.uniform(0.9, 2.2)
                reason = "incomplete_wetting"
            elif attempt == 1 and test_type != "post_use" and self.rng.random() < C.RANDOM_CONNECTION_FAIL:
                value = limit + self.rng.uniform(0.2, 1.5)
                reason = "connection_leak"
                self.alarm(cart, t + td(seconds=70), "A-210", "Pressure decay high during stabilization")
            faulted = self.rng.random() < C.FAULTED_TEST_RATE
            if faulted:
                reason = "test_fault"
                self.alarm(cart, t + td(seconds=60), "A-990", "Test aborted - supply pressure unstable")
            if leak and self.rng.random() < 0.3:
                self.alarm(cart, t + td(seconds=80), "A-205", "Pressure stability warning")
            reported = 0.0 if faulted else round(value * factor, 3)
            duration = td(seconds=self.rng.uniform(170, 200))
            passed = (not faulted) and reported <= limit
            self.t.attempts.append({
                "assembly_id": a["assembly_id"], "cart_id": cart, "line": a["line"], "test_type": test_type,
                "attempt": attempt, "start": t, "end": t + duration, "true_flow": round(value, 3),
                "reported_flow": reported, "faulted": faulted, "passed": passed,
                "wetting_time_s": round(wet, 1) if wet is not None else None,
                "reason": reason, "pressure_factor": factor, "leak": leak, "scenario_tags": ";".join(tags)})
            t += duration
            if passed or attempt >= 3:
                return t, ("PASS" if passed else "FAIL"), attempt, reported
            if reason == "incomplete_wetting":
                wet = self.rng.uniform(85, 115)
                t += td(seconds=wet + 120)
            else:
                t += td(minutes=self.rng.uniform(4, 9))

    def wetting_time(self, line: str, t: dt.datetime, crew: str) -> float:
        d = day_of(t)
        s3 = C.SCENARIOS["S3_incomplete_wetting"]
        rate = s3["base_rate"]
        if crew == s3["crew"] and s3["start_day"] <= d < s3["end_day"]:
            rate = s3["crew_rate"]
        if self.rng.random() < rate:
            return float(self.rng.uniform(25, 55))
        return float(self.rng.uniform(80, 110))

    def build_assembly(self, cart: str, batch: dict, build_start: dt.datetime, is_replacement: bool) -> dict:
        line = cart[5]
        self.cart_count[cart] += 1
        self.since_seal[cart] += 1
        vendor, lot = self.filter_lot(line, build_start)
        pre_start = build_start + td(minutes=self.rng.uniform(30, 55))
        crew = self.crew(line, pre_start)
        wet = self.wetting_time(line, pre_start, crew)
        a = {"assembly_id": f"ASM-{cart[5:]}-{self.cart_count[cart]:05d}", "cart_id": cart, "line": line,
             "role": C.CART_ROLES[cart[-1]], "batch_id": batch["batch_id"], "filter_vendor": vendor,
             "filter_lot": lot, "build_start": build_start, "pre_it_start": pre_start + td(seconds=wet),
             "wetting_time_s": wet, "crew": crew, "is_replacement": is_replacement}
        self.t.filter_usage.append({"batch_id": batch["batch_id"], "assembly_id": a["assembly_id"], "line": line,
                                    "vendor": vendor, "lot": lot, "used_at": build_start})
        return a

    def run_pre(self, a: dict) -> None:
        a["_true"] = self.true_flows(a["cart_id"], a["pre_it_start"], a["filter_lot"])
        end, res, n, val = self.run_test(a, "pre_it", a["pre_it_start"], a["_true"]["pre"],
                                         C.SPEC["pre_it_max_ml_min"], a["wetting_time_s"])
        a.update({"_pre_end": end, "pre_it_result": res, "pre_it_attempts": n, "pre_it_flow": val})

    def run_pupsit(self, a: dict, cyc: dict) -> None:
        if cyc["overtemp_fault"]:
            a["_true"]["pup"] += self.rng.uniform(*C.SCENARIOS["S4_autoclave_overtemp"]["pupsit_shift"])
            a["_true"]["post"] = a["_true"]["pup"] + self.rng.uniform(0.05, 0.35)
            a["_true"]["tags"] = a["_true"]["tags"] + ["S4_autoclave_overtemp"]
        # Re-wet after sterilization: the autoclave dries the membrane.
        wet_start = cyc["end"] + td(minutes=self.rng.uniform(10, 45))
        wet = self.wetting_time(a["line"], wet_start, self.crew(a["line"], wet_start))
        start = wet_start + td(seconds=wet + 60)
        end, res, n, val = self.run_test(a, "pupsit", start, a["_true"]["pup"], C.SPEC["pupsit_max_ml_min"], wet)
        a.update({"autoclave_cycle_id": cyc["cycle_id"], "pupsit_start": start, "_pupsit_end": end,
                  "pupsit_wetting_time_s": wet,
                  "pupsit_result": res, "pupsit_attempts": n, "pupsit_flow": val,
                  "scenario_tags": ";".join(dict.fromkeys(a["_true"]["tags"]))})

    def autoclave_cycle(self, line: str, start: dt.datetime, n_loads: int) -> dict:
        ac = C.AUTOCLAVE_FOR_LINE[line]
        fault = ac == "AC-02" and self.active("S4_autoclave_overtemp", day_of(start))
        max_temp = self.rng.uniform(*C.SCENARIOS["S4_autoclave_overtemp"]["max_temp_c"]) if fault \
            else self.rng.normal(122.2, 0.5)
        hold = self.rng.uniform(40, 50) if fault else self.rng.uniform(30, 33)
        cyc = {"cycle_id": f"{ac}-{len(self.t.autoclave_cycles) + 1:05d}", "autoclave_id": ac, "line": line,
               "start": start, "end": start + td(minutes=45 + hold + self.rng.uniform(140, 170)),
               "max_temp_c": round(float(max_temp), 2), "hold_minutes": round(float(hold), 1),
               "loads": n_loads, "overtemp_fault": fault}
        self.t.autoclave_cycles.append(cyc)
        return cyc

    def deviation(self, a: dict, batch: dict) -> None:
        failed = "PUPSIT" if a.get("pupsit_result") == "FAIL" else "Pre-IT"
        opened = a.get("_pupsit_end", a["_pre_end"]) + td(hours=self.rng.uniform(1, 20))
        tags = a["_true"]["tags"]
        if any(s in tags for s in ("S1_cart_seal_wear", "S10_seal_wear_recurrence")):
            hypo = "Suspect filter capsule lot quality; recent lot change."
            root = "Gas leak at cart inlet manifold due to worn inlet seal. Seal kit replaced; cart leak test " \
                   "passed. CAPA: add seal inspection to monthly checks; trend PUPSIT per cart."
        elif "S2_bad_filter_lot" in tags:
            hypo = "Possible cart leak or assembly error; re-test performed."
            root = "Filter capsule lot defect confirmed by supplier investigation (membrane). Lot quarantined; " \
                   "supplier complaint raised."
        elif "S4_autoclave_overtemp" in tags:
            hypo = "PUPSIT failure after sterilization; investigation pending."
            root = "Autoclave temperature overshoot damaged membranes. Temperature probe replaced and " \
                   "controller retuned; affected cycles reviewed."
        else:
            hypo = "Under investigation."
            root = "No assignable root cause; assembly replaced and batch continued."
        self.t.deviations.append({
            "batch_id": batch["batch_id"], "line": batch["line"], "assembly_id": a["assembly_id"],
            "cart_id": a["cart_id"], "category": "Filter integrity test failure", "failed_test": failed,
            "opened_at": opened, "published_at": opened + td(hours=self.rng.uniform(24, 120)),
            "closed_at": opened + td(days=self.rng.uniform(15, 45)), "initial_assessment": hypo,
            "root_cause": root, "scenario_tags": ";".join(tags)})

    # ------------------------------------------------------------ batch
    def simulate_batch(self, line: str, process_start: dt.datetime) -> dt.datetime:
        options = C.PRODUCTS[line]
        product, volume = options[int(self.rng.integers(0, len(options)))]
        batch = {"batch_id": f"B{next(self.batch_ids)}", "line": line, "product": product,
                 "fill_volume_ml": volume, "process_start": process_start, "crew": self.crew(line, process_start)}
        asm = [self.build_assembly(f"FITC-{line}{n}", batch, process_start + td(minutes=self.rng.uniform(0, 20)), False)
               for n in "12"]
        for a in asm:
            self.run_pre(a)
        cyc = self.autoclave_cycle(line, max(a["_pre_end"] for a in asm) + td(minutes=self.rng.uniform(15, 35)), 2)
        final, status = [], "COMPLETED"
        for a in asm:
            self.run_pupsit(a, cyc)
            cur = a
            if "FAIL" in (a["pre_it_result"], a["pupsit_result"]):
                self.deviation(a, batch)
                rep = self.build_assembly(a["cart_id"], batch, a["_pupsit_end"] + td(minutes=30), True)
                self.run_pre(rep)
                self.run_pupsit(rep, self.autoclave_cycle(line, rep["_pre_end"] + td(minutes=20), 1))
                if "FAIL" in (rep["pre_it_result"], rep["pupsit_result"]):
                    self.deviation(rep, batch)
                    status = "CANCELLED"
                self.t.assemblies.append(a)
                cur = rep
            final.append(cur)
        fill_start = max(a["_pupsit_end"] for a in final) + td(minutes=self.rng.uniform(15, 40))
        fill_hours = float(self.rng.uniform(18, 28)) if status == "COMPLETED" else 0.0
        fill_end = fill_start + td(hours=fill_hours)
        tubs = int(fill_hours * self.rng.uniform(95, 115))
        batch.update({"fill_start": fill_start, "fill_end": fill_end, "status": status, "tubs": tubs})
        for a in final:
            if status == "COMPLETED":
                start = fill_end + td(minutes=self.rng.uniform(10, 45))
                end, res, n, val = self.run_test(a, "post_use", start, a["_true"]["post"],
                                                 C.SPEC["post_use_max_ml_min"], None)
                a.update({"post_use_result": res, "post_use_attempts": n, "post_use_flow": val, "post_use_end": end})
            self.t.assemblies.append(a)
        if status == "COMPLETED":
            self.stations(line, batch)
        rejects = int(tubs * C.SYRINGES_PER_TUB * self.rng.uniform(0.002, 0.008))
        comment = ""
        if status == "CANCELLED":
            comment = "Batch cancelled - filter integrity failure on replacement assembly"
        elif any(a["is_replacement"] for a in final):
            comment = str(self.rng.choice(["FITC re-test, assembly replaced", "Delay - filter assy replaced",
                                           "Start delayed, IT fail"]))
        elif self.rng.random() < 0.08:
            comment = str(self.rng.choice(["Delay - waiting QA release", "Short stop - TRR jam",
                                           "Shift handover delay", "Material staging late"]))
        batch.update({"total_good": tubs * C.SYRINGES_PER_TUB - rejects, "rejects": rejects, "comment": comment,
                      "process_end": max([fill_end] + [a.get("post_use_end", fill_end) for a in final])})
        self.t.batches.append(batch)
        return batch["process_end"]

    # ------------------------------------------------------------ stations (vectorised)
    def stations(self, line: str, batch: dict) -> None:
        rng = self.rng
        start, end = batch["fill_start"], batch["fill_end"]
        d0 = day_of(start)
        hours = (end - start).total_seconds() / 3600
        # Tyvek removal alarms
        s7 = C.SCENARIOS["S7_tyvek_gripper_wear"]
        in_s7 = line == "A" and self.active("S7_tyvek_gripper_wear", d0)
        rate = C.TYVEK_BASE_ALARM_RATE
        if in_s7:
            rate += (s7["alarm_rate_peak"] - rate) * (d0 - s7["start_day"]) / (s7["fix_day"] - s7["start_day"])
        codes = ["TRR-101 LID_NOT_REMOVED", "TRR-102 LINER_TEAR", "TRR-103 CUP_VACUUM_LOW"]
        for _ in range(rng.binomial(batch["tubs"], rate)):
            code = codes[2] if in_s7 and rng.random() < 0.7 else str(rng.choice(codes, p=[0.5, 0.3, 0.2]))
            self.t.tyvek_alarms.append({
                "alarm_time": start + td(hours=rng.uniform(0, hours)), "line": line, "robot_id": f"TRR-{line}",
                "batch_id": batch["batch_id"], "tub_id": f"TUB-{batch['batch_id'][1:]}-{rng.integers(1, max(batch['tubs'], 2)):04d}",
                "alarm_code": code, "cleared_after_min": round(float(rng.uniform(1, 4) * (2.5 if in_s7 else 1)), 1),
                "scenario_tags": "S7_tyvek_gripper_wear" if in_s7 and code == codes[2] else ""})
        times = pd.date_range(start, end, freq="30min", inclusive="left")
        if len(times) == 0:
            return
        days = np.array([day_of(t) for t in times])
        # Filling checks: times x needles
        target = round(batch["fill_volume_ml"] * C.FILL_DENSITY_MG_PER_ML, 1)
        n_t, n_n = len(times), C.FILLER_NEEDLES
        w = target + rng.normal(0, 1.2, n_n)[None, :] + rng.normal(0, target * 0.004, (n_t, n_n))
        tag = np.full((n_t, n_n), "", dtype=object)
        s8 = C.SCENARIOS["S8_filler_needle_underfill"]
        if line == "B":
            m = (days >= s8["start_day"]) & (days < s8["fix_day"])
            frac = (days - s8["start_day"]) / (s8["fix_day"] - s8["start_day"])
            w[m, 6] += s8["max_bias_mg"] * frac[m] * (target / 1020)
            tag[m, 6] = "S8_filler_needle_underfill"
        self.t.filling_frames.append(pd.DataFrame({
            "check_time": np.repeat(times.values, n_n), "line": line, "filler_id": f"FILLER-{line}",
            "batch_id": batch["batch_id"], "needle": np.tile(np.arange(1, n_n + 1), n_t),
            "fill_weight_mg": w.ravel().round(1), "target_mg": target, "scenario_tags": tag.ravel()}))
        # Stoppering checks: times x stations
        n_s = len(C.STOPPER_STATIONS)
        vac = rng.normal(90, 6, (n_t, n_s))
        sd = np.full((n_t, n_s), 0.12)
        stag = np.full((n_t, n_s), "", dtype=object)
        s9 = C.SCENARIOS["S9_vacuum_pump_degradation"]
        if line == "A":
            m = (days >= s9["start_day"]) & (days < s9["fix_day"])
            frac = ((days - s9["start_day"]) / (s9["fix_day"] - s9["start_day"]))[:, None]
            vac = np.where(m[:, None], vac + s9["max_vacuum_rise_mbar"] * frac, vac)
            sd = np.where(m[:, None], 0.12 + 0.25 * frac, sd)
            stag[m, :] = "S9_vacuum_pump_degradation"
        self.t.stopper_frames.append(pd.DataFrame({
            "check_time": np.repeat(times.values, n_s), "line": line, "station": np.tile(C.STOPPER_STATIONS, n_t),
            "vacuum_pump": f"VAC-{line}", "batch_id": batch["batch_id"], "vacuum_mbar_abs": vac.ravel().round(1),
            "plunger_depth_mm": rng.normal(8.0, sd).ravel().round(3), "scenario_tags": stag.ravel()}))

    # ------------------------------------------------------------ maintenance
    def work_orders(self) -> None:
        rng = self.rng
        wo = [700100]
        equipment = (C.CARTS + ["AC-01", "AC-02"] + [f"TRR-{l}" for l in C.LINES]
                     + [f"FILLER-{l}" for l in C.LINES] + [f"VAC-{l}" for l in C.LINES])
        mundane = {
            "FITC": [("Display blank", "reseated cable, ok", "NOF"), ("printer jam", "cleared jam", "NOF"),
                     ("castor loose", "tightend castor", "WEAR"), ("chk readings", "chkd, no issue found", "NOF")],
            "AC": [("door gasket chk after alarm", "NFF", "NOF"), ("chart rec pen", "rplcd pen", "WEAR")],
            "TRR": [("light curtain fault", "realigned LC", "ADJ"), ("HMI touch", "recal touch panel", "ADJ")],
            "FILLER": [("needle guard sensor", "cleaned sensor", "NOF"), ("star wheel noise", "lubed", "WEAR")],
            "VAC": [("exhaust filter", "rplcd exhaust filter", "WEAR"), ("oil low", "topped up oil", "WEAR")],
        }

        def add(eq, wtype, day, desc, long_desc, fcode="", tags=""):
            wo[0] += int(rng.integers(1, 40))
            created = C.START + td(days=day, hours=rng.uniform(1, 10))
            self.t.work_orders.append({"wo_number": wo[0], "equipment": eq, "work_type": wtype, "created": created,
                                       "actual_finish": created + td(hours=rng.uniform(2, 60)),
                                       "description": desc, "long_description": long_desc, "failure_code": fcode,
                                       "scenario_tags": tags})

        for eq in equipment:
            day = float(rng.uniform(5, 40))
            while day < C.DAYS:
                if eq.startswith("FITC"):
                    add(eq, "PMCAL", day, str(rng.choice(["Qtrly cal - P & flow xducer", "PMCAL pressure/flow",
                                                          "Calibration FITC"])),
                        "Cal vs ref std. As found in tol.", "CAL")
                else:
                    add(eq, "PM", day, "PM", str(rng.choice(["PM checklist done", "Routine PM ok", "PM done - no abn"])))
                day += float(rng.uniform(55, 75))
            for _ in range(int(rng.integers(1, 6))):
                desc, ld, fc = mundane[eq.split("-")[0]][int(rng.integers(0, len(mundane[eq.split('-')[0]])))]
                add(eq, "CM", float(rng.uniform(0, C.DAYS)), desc, ld, fc)
        for cart in C.CARTS:  # yearly seal kit PM
            for d in self.seal_pm_day[cart]:
                add(cart, "PM", d, "Annual seal kit", "Annual seal kit rplcd per PM schedule. LT passed.", "WEAR")

        s = C.SCENARIOS
        f1, f10 = s["S1_cart_seal_wear"]["fix_day"], s["S10_seal_wear_recurrence"]["fix_day"]
        add("FITC-B2", "CM", s["S1_cart_seal_wear"]["start_day"] + 9, "readings high?",
            "Opr reports higher flow values. Visual chk ok, no action.", "NOF", "S1_cart_seal_wear")
        add("FITC-B2", "CM", f1 - 0.5, "PUPSIT fail - leak chk",
            "LT on cart: leak at inlet manifold. Inlet seal flattened. Rplcd seal kit, LT passed.", "LEAK",
            "S1_cart_seal_wear")
        add("FITC-A2", "CM", f10 - 0.5, "IT fail FITC",
            "Leak found inlet side, seal worn. rplcd seal kit. LT ok.", "LEAK", "S10_seal_wear_recurrence")
        add("FITC-C1", "PMCAL", s["S5_sensor_drift"]["fix_day"] - 0.5, "Cal - flow xducer OOT",
            "As found flow xducer reading approx 30% low vs ref. Adjusted, recal. As left in tol.", "CAL",
            "S5_sensor_drift")
        add("AC-02", "CM", s["S4_autoclave_overtemp"]["fix_day"] - 0.5, "temp overshoot alarms",
            "Chamber temp overshooting SP. Rplcd temp probe, retuned ctrl. Verif cycle passed.", "WEAR",
            "S4_autoclave_overtemp")
        add("TRR-A", "CM", s["S7_tyvek_gripper_wear"]["fix_day"] - 0.5, "lid removal alarms freq",
            "vac cups worn/cracked. rplcd 6 cups.", "WEAR", "S7_tyvek_gripper_wear")
        add("FILLER-B", "CM", s["S8_filler_needle_underfill"]["fix_day"] - 0.5, "N7 low fill wt",
            "Dosing pump 7 piston seal worn, rplcd. Gravimetric chk ok.", "WEAR", "S8_filler_needle_underfill")
        add("VAC-A", "PM", s["S9_vacuum_pump_degradation"]["fix_day"] - 0.5, "Vac pump service",
            "Vanes worn, ult vacuum low. Rplcd vanes + oil.", "WEAR", "S9_vacuum_pump_degradation")

    # ------------------------------------------------------------ orchestration
    def seal_reset(self, cart: str, d: float) -> None:
        resets = list(self.seal_pm_day[cart]) + [
            C.SCENARIOS[s]["fix_day"] for s in ("S1_cart_seal_wear", "S10_seal_wear_recurrence")
            if C.SCENARIOS[s]["entity"] == cart]
        last = getattr(self, "_last_reset", {}).get(cart, -1)
        due = [r for r in resets if last < r <= d]
        if due:
            self.since_seal[cart] = 0
            self._last_reset = {**getattr(self, "_last_reset", {}), cart: max(due)}

    def run(self) -> Truth:
        end_time = C.START + td(days=C.DAYS)
        for line in C.LINES:
            t = C.START + td(hours=self.rng.uniform(0, 6))
            while t < end_time - td(days=2):
                d = day_of(t)
                shut = [w for w in C.SITE_SHUTDOWNS + C.PLANNED_SHUTDOWNS.get(line, []) if w[0] <= d < w[1]]
                if shut:
                    t = C.START + td(days=shut[0][1], hours=self.rng.uniform(0, 4))
                    continue
                for n in "12":
                    self.seal_reset(f"FITC-{line}{n}", d)
                t = self.simulate_batch(line, t) + td(hours=self.rng.uniform(5, 10))
        h = C.START
        while h < end_time:
            for line in C.LINES:
                self.t.environment.append({"timestamp": h, "line": line, "room_temp_c": self.room_temp(line, h),
                                           "rel_humidity_pct": round(float(self.rng.normal(42, 3)), 1)})
            h += td(hours=1)
        self.work_orders()
        return self.t
