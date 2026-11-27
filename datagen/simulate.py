"""Truth simulation: what physically happened on the line.

Produces clean pandas DataFrames with exact timestamps and IDs. Nothing here is
written to data/raw directly; export.py turns these into messy source-system
files. Keeping truth and export separate means every messy file can be checked
against a known answer.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config as C

H = dt.timedelta(hours=1)
MIN = dt.timedelta(minutes=1)


def day_of(t: dt.datetime) -> float:
    return (t - C.START).total_seconds() / 86400


@dataclass
class Truth:
    batches: list = field(default_factory=list)
    assemblies: list = field(default_factory=list)
    attempts: list = field(default_factory=list)
    autoclave_cycles: list = field(default_factory=list)
    filter_usage: list = field(default_factory=list)
    work_orders: list = field(default_factory=list)
    deviations: list = field(default_factory=list)
    tyvek_alarms: list = field(default_factory=list)
    filling_checks: list = field(default_factory=list)
    stopper_checks: list = field(default_factory=list)
    environment: list = field(default_factory=list)

    def frames(self) -> dict[str, pd.DataFrame]:
        return {k: pd.DataFrame(v) for k, v in self.__dict__.items()}


class Simulator:
    def __init__(self, seed: int = C.SEED):
        self.rng = np.random.default_rng(seed)
        self.t = Truth()
        self.cart_assembly_count = {c: 0 for c in C.CARTS}
        self.batch_ids = iter(self.rng.choice(np.arange(400000, 999999), 2000, replace=False))
        self.temp_cache: dict[tuple, float] = {}

    # ------------------------------------------------------------------ helpers
    def in_window(self, scen: str, day: float, end_key: str = "fix_day") -> bool:
        s = C.SCENARIOS[scen]
        end = s.get(end_key, s.get("end_day"))
        return s["start_day"] <= day < end

    def room_temp(self, line: str, t: dt.datetime) -> float:
        key = (line, t.replace(minute=0, second=0, microsecond=0))
        if key not in self.temp_cache:
            d = day_of(key[1])
            base = 21.0 + 0.6 * np.sin(2 * np.pi * key[1].hour / 24)
            if line == "A" and self.in_window("S6_warm_room", d, "end_day"):
                lo, hi = C.SCENARIOS["S6_warm_room"]["temp_c"]
                base = self.rng.uniform(lo, hi)
            self.temp_cache[key] = round(base + self.rng.normal(0, 0.3), 2)
        return self.temp_cache[key]

    def filter_lot(self, line: str, t: dt.datetime) -> tuple[str, str]:
        """Pick vendor + lot for a filter capsule used at time t on a line."""
        d = day_of(t)
        s2, rh = C.SCENARIOS["S2_bad_filter_lot"], C.SCENARIOS["RH1_new_lot_coincidence"]
        if line in s2["lines"] and s2["start_day"] <= d < s2["end_day"] and self.rng.random() < 0.85:
            return s2["vendor"], s2["entity"]
        if line in rh["lines"] and rh["start_day"] <= d < rh["end_day"] and self.rng.random() < 0.8:
            return rh["vendor"], rh["entity"]
        vendor = "V-FLT-01" if self.rng.random() < C.FILTER_VENDORS["V-FLT-01"]["share"] else "V-FLT-02"
        period = int(d // C.LOT_ROTATION_DAYS)
        prefix = "VL1" if vendor == "V-FLT-01" else "VL2"
        lot = f"{prefix}-{(C.START + dt.timedelta(days=period * C.LOT_ROTATION_DAYS)).strftime('%m%d')}"
        if lot in (s2["entity"], rh["entity"]):
            lot += "B"
        return vendor, lot

    def autoclave_cycle(self, line: str, start: dt.datetime, batch_id: str, n_loads: int) -> dict:
        ac = C.AUTOCLAVE_FOR_LINE[line]
        d = day_of(start)
        fault = ac == "AC-02" and self.in_window("S4_autoclave_overtemp", d)
        max_temp = self.rng.uniform(*C.SCENARIOS["S4_autoclave_overtemp"]["max_temp_c"]) if fault \
            else self.rng.normal(122.2, 0.5)
        hold = self.rng.uniform(40, 50) if fault else self.rng.uniform(30, 33)
        end = start + dt.timedelta(minutes=45 + hold + self.rng.uniform(140, 170))
        cyc = {
            "cycle_id": f"{ac}-{len(self.t.autoclave_cycles) + 1:05d}",
            "autoclave_id": ac, "line": line, "batch_id": batch_id, "start": start, "end": end,
            "max_temp_c": round(max_temp, 2), "hold_minutes": round(hold, 1),
            "loads": n_loads, "overtemp_fault": fault,
        }
        self.t.autoclave_cycles.append(cyc)
        return cyc

    # --------------------------------------------------------- integrity tests
    def true_flows(self, cart: str, t: dt.datetime, lot: str, vendor: str, cyc: dict | None = None) -> dict:
        line = cart[5]
        d = day_of(t)
        pm, psd, um, usd = C.BASELINE[cart]
        temp = self.room_temp(line, t)
        shared = self.rng.normal(0, 1)  # weak shared component -> weak correlation
        pre = pm + 0.012 * (temp - 21) + psd * (0.35 * shared + 0.94 * self.rng.normal())
        pup = um + 0.04 * (temp - 21) + usd * (0.35 * shared + 0.94 * self.rng.normal())
        tags = []

        s1 = C.SCENARIOS["S1_cart_seal_wear"]
        if cart == s1["entity"] and self.in_window("S1_cart_seal_wear", d):
            k = self.cart_assembly_count[cart] - self.s1_start_index
            pre += s1["pre_it_slope_per_assembly"] * k
            pup += s1["pupsit_slope_per_assembly"] * k
            tags.append("S1_cart_seal_wear")
        s2 = C.SCENARIOS["S2_bad_filter_lot"]
        if lot == s2["entity"]:
            pre += self.rng.uniform(*s2["pre_it_shift"])
            pup += self.rng.uniform(*s2["pupsit_shift"])
            tags.append("S2_bad_filter_lot")
        # S4 (autoclave damage) is applied later in _run_pupsit, because the
        # sterilization cycle happens after pre-IT.
        if line == "A" and self.in_window("S6_warm_room", d, "end_day"):
            tags.append("S6_warm_room")
        if lot == C.SCENARIOS["RH1_new_lot_coincidence"]["entity"]:
            tags.append("RH1_new_lot_coincidence")

        factor = 1.0
        s5 = C.SCENARIOS["S5_sensor_drift"]
        if cart == s5["entity"] and self.in_window("S5_sensor_drift", d):
            factor = 1 + s5["reported_factor_per_day"] * (d - s5["start_day"])
            tags.append("S5_sensor_drift")
        post = pup + self.rng.uniform(0.05, 0.35)
        return {"pre": max(pre, 0.2), "pup": max(pup, 1.0), "post": post,
                "factor": factor, "temp": temp, "tags": tags}

    def run_test(self, assembly_id: str, cart: str, test_type: str, start: dt.datetime,
                 true_value: float, factor: float, limit: float, wetting_s: float | None,
                 tags: list) -> tuple[dt.datetime, str, int, float]:
        """Simulate attempts for one test. Returns (end_time, result, attempts, final_reported)."""
        t = start
        attempt = 0
        line = cart[5]
        d = day_of(start)
        wet = wetting_s
        while True:
            attempt += 1
            reason = "normal"
            value = true_value + self.rng.normal(0, 0.03)
            if test_type == "pre_it" and attempt == 1 and wet is not None and wet < C.SPEC["wetting_min_s"]:
                value = true_value + self.rng.uniform(0.9, 2.2)
                reason = "incomplete_wetting"
            elif attempt == 1 and self.rng.random() < C.RANDOM_CONNECTION_FAIL and test_type != "post_use":
                value = limit + self.rng.uniform(0.2, 1.5)
                reason = "connection_leak"
            faulted = self.rng.random() < C.FAULTED_TEST_RATE
            reported = 0.0 if faulted else round(value * factor, 3)
            if faulted:
                reason = "test_fault"
            duration = dt.timedelta(seconds=float(self.rng.uniform(170, 200)))
            passed = (not faulted) and reported <= limit
            self.t.attempts.append({
                "assembly_id": assembly_id, "cart_id": cart, "line": line, "test_type": test_type,
                "attempt": attempt, "start": t, "end": t + duration, "true_flow": round(value, 3),
                "reported_flow": reported, "faulted": faulted, "passed": passed,
                "wetting_time_s": round(wet, 1) if (wet is not None and test_type == "pre_it") else None,
                "reason": reason, "pressure_factor": factor,
                "leak": "S1_cart_seal_wear" in tags, "scenario_tags": ";".join(tags),
            })
            t = t + duration
            if passed or attempt >= 3:
                return t, ("PASS" if passed else "FAIL"), attempt, reported
            if reason == "incomplete_wetting":
                wet = self.rng.uniform(85, 115)  # operator re-wets properly
                t += dt.timedelta(seconds=wet + 120)
            else:
                t += dt.timedelta(minutes=float(self.rng.uniform(4, 9)))

    def wetting_time(self, line: str, t: dt.datetime) -> float:
        d = day_of(t)
        s3 = C.SCENARIOS["S3_incomplete_wetting"]
        rate = s3["base_rate"]
        if line == "C" and s3["line_c_start_day"] <= d < s3["line_c_end_day"]:
            rate = s3["line_c_rate"]
        if self.rng.random() < rate:
            return float(self.rng.uniform(25, 55))
        return float(self.rng.uniform(80, 110))

    def build_assembly(self, cart: str, batch: dict, build_start: dt.datetime,
                       is_replacement: bool) -> dict:
        line = cart[5]
        self.cart_assembly_count[cart] += 1
        vendor, lot = self.filter_lot(line, build_start)
        aid = f"ASM-{cart[5:]}-{self.cart_assembly_count[cart]:04d}"
        pre_start = build_start + dt.timedelta(minutes=float(self.rng.uniform(30, 55)))
        wet = self.wetting_time(line, pre_start)
        return {"assembly_id": aid, "cart_id": cart, "line": line, "role": C.CART_ROLES[cart[-1]],
                "batch_id": batch["batch_id"], "filter_vendor": vendor, "filter_lot": lot,
                "build_start": build_start, "pre_it_start": pre_start + dt.timedelta(seconds=wet),
                "wetting_time_s": wet, "is_replacement": is_replacement}

    # ----------------------------------------------------------- line stations
    def simulate_batch(self, line: str, process_start: dt.datetime, prev_end: dt.datetime) -> dt.datetime:
        product, volume = PRODUCT_PICK(self.rng, line)
        batch = {"batch_id": f"B{next(self.batch_ids)}", "line": line, "product": product,
                 "fill_volume_ml": volume, "process_start": process_start}
        carts = [f"FITC-{line}1", f"FITC-{line}2"]
        asm = [self.build_assembly(c, batch, process_start + dt.timedelta(minutes=float(self.rng.uniform(0, 20))), False)
               for c in carts]
        # Pre-IT for both assemblies
        for a in asm:
            a["_pre_end"], a["pre_it_result"], a["pre_it_attempts"], a["pre_it_flow"] = (None,) * 4
        cyc_start_candidates = []
        for a in asm:
            self._run_pre(a)
            cyc_start_candidates.append(a["_pre_end"])
        cyc = self.autoclave_cycle(line, max(cyc_start_candidates) + dt.timedelta(minutes=float(self.rng.uniform(15, 35))),
                                   batch["batch_id"], len(asm))
        ready_times, final_asm, status = [], [], "COMPLETED"
        for a in asm:
            a = self._run_pupsit(a, cyc)
            cur = a
            if a["pupsit_result"] == "FAIL" or a["pre_it_result"] == "FAIL":
                self._deviation(a, batch)
                # one replacement assembly with a fresh filter
                rep = self.build_assembly(a["cart_id"], batch, a["_pupsit_end"] + dt.timedelta(minutes=30), True)
                self._run_pre(rep)
                rcyc = self.autoclave_cycle(line, rep["_pre_end"] + dt.timedelta(minutes=20), batch["batch_id"], 1)
                rep = self._run_pupsit(rep, rcyc)
                if rep["pupsit_result"] == "FAIL" or rep["pre_it_result"] == "FAIL":
                    self._deviation(rep, batch)
                    status = "CANCELLED"
                self.t.assemblies.append(a)
                cur = rep
            final_asm.append(cur)
            ready_times.append(cur["_pupsit_end"])
        fill_start = max(ready_times) + dt.timedelta(minutes=float(self.rng.uniform(15, 40)))
        fill_hours = float(self.rng.uniform(18, 28)) if status == "COMPLETED" else 0.0
        fill_end = fill_start + dt.timedelta(hours=fill_hours)
        tubs = int(fill_hours * self.rng.uniform(95, 115))
        batch.update({"fill_start": fill_start, "fill_end": fill_end, "status": status, "tubs": tubs})

        if status == "COMPLETED":
            for a in final_asm:
                limit = C.SPEC["post_use_max_ml_min"]
                start = fill_end + dt.timedelta(minutes=float(self.rng.uniform(10, 45)))
                end, res, n, val = self.run_test(a["assembly_id"], a["cart_id"], "post_use", start,
                                                 a["_true"]["post"], a["_true"]["factor"], limit, None, a["_true"]["tags"])
                a.update({"post_use_result": res, "post_use_attempts": n, "post_use_flow": val, "post_use_end": end})
            self._stations(line, batch)
        for a in final_asm:
            a.setdefault("post_use_result", None)
            self.t.assemblies.append(a)
        rejects = int(tubs * C.SYRINGES_PER_TUB * self.rng.uniform(0.002, 0.008))
        batch.update({"total_good": tubs * C.SYRINGES_PER_TUB - rejects, "rejects": rejects,
                      "process_end": max([fill_end] + [a.get("post_use_end", fill_end) for a in final_asm])})
        self.t.batches.append(batch)
        return batch["process_end"]

    def _run_pre(self, a: dict) -> None:
        cyc_stub = {"overtemp_fault": False}
        a["_true"] = self.true_flows(a["cart_id"], a["pre_it_start"], a["filter_lot"], a["filter_vendor"], cyc_stub)
        end, res, n, val = self.run_test(a["assembly_id"], a["cart_id"], "pre_it", a["pre_it_start"],
                                         a["_true"]["pre"], a["_true"]["factor"], C.SPEC["pre_it_max_ml_min"],
                                         a["wetting_time_s"], a["_true"]["tags"])
        a.update({"_pre_end": end, "pre_it_result": res, "pre_it_attempts": n, "pre_it_flow": val})
        self.t.filter_usage.append({"batch_id": a["batch_id"], "assembly_id": a["assembly_id"], "line": a["line"],
                                    "vendor": a["filter_vendor"], "lot": a["filter_lot"], "used_at": a["build_start"]})

    def _run_pupsit(self, a: dict, cyc: dict) -> dict:
        if cyc["overtemp_fault"]:
            a["_true"]["pup"] += self.rng.uniform(*C.SCENARIOS["S4_autoclave_overtemp"]["pupsit_shift"])
            a["_true"]["post"] = a["_true"]["pup"] + self.rng.uniform(0.05, 0.35)
            a["_true"]["tags"] = a["_true"]["tags"] + ["S4_autoclave_overtemp"]
        start = cyc["end"] + dt.timedelta(minutes=float(self.rng.uniform(10, 45)))
        end, res, n, val = self.run_test(a["assembly_id"], a["cart_id"], "pupsit", start, a["_true"]["pup"],
                                         a["_true"]["factor"], C.SPEC["pupsit_max_ml_min"], None, a["_true"]["tags"])
        a.update({"autoclave_cycle_id": cyc["cycle_id"], "pupsit_start": start, "_pupsit_end": end,
                  "pupsit_result": res, "pupsit_attempts": n, "pupsit_flow": val,
                  "scenario_tags": ";".join(dict.fromkeys(a["_true"]["tags"]))})
        return a

    def _deviation(self, a: dict, batch: dict) -> None:
        failed = "PUPSIT" if a.get("pupsit_result") == "FAIL" else "Pre-IT"
        opened = a.get("_pupsit_end", a["_pre_end"]) + dt.timedelta(hours=float(self.rng.uniform(1, 20)))
        tags = a["_true"]["tags"]
        if "S1_cart_seal_wear" in tags:
            hypothesis = "Suspect filter capsule lot quality; recent lot change on line B."  # wrong on purpose
        elif "S2_bad_filter_lot" in tags:
            hypothesis = "Possible cart leak or assembly error; re-test performed."  # wrong on purpose
        elif "S4_autoclave_overtemp" in tags:
            hypothesis = "PUPSIT failure after sterilization; investigation pending."
        else:
            hypothesis = "Under investigation."
        self.t.deviations.append({
            "batch_id": batch["batch_id"], "line": batch["line"], "assembly_id": a["assembly_id"],
            "cart_id": a["cart_id"], "category": "Filter integrity test failure", "failed_test": failed,
            "opened_at": opened, "published_at": opened + dt.timedelta(hours=float(self.rng.uniform(24, 120))),
            "initial_assessment": hypothesis, "scenario_tags": ";".join(tags)})

    def _stations(self, line: str, batch: dict) -> None:
        start, end = batch["fill_start"], batch["fill_end"]
        hours = (end - start).total_seconds() / 3600
        # Tyvek removal alarms
        rate = C.TYVEK_BASE_ALARM_RATE
        s7 = C.SCENARIOS["S7_tyvek_gripper_wear"]
        d = day_of(start)
        in_s7 = line == "A" and self.in_window("S7_tyvek_gripper_wear", d)
        if in_s7:
            frac = (d - s7["start_day"]) / (s7["fix_day"] - s7["start_day"])
            rate = rate + (s7["alarm_rate_peak"] - rate) * frac
        n = self.rng.binomial(batch["tubs"], rate)
        codes = ["TRR-101 LID_NOT_REMOVED", "TRR-102 LINER_TEAR", "TRR-103 CUP_VACUUM_LOW"]
        for _ in range(n):
            at = start + dt.timedelta(hours=float(self.rng.uniform(0, hours)))
            code = codes[2] if in_s7 and self.rng.random() < 0.7 else self.rng.choice(codes, p=[0.5, 0.3, 0.2])
            self.t.tyvek_alarms.append({
                "alarm_time": at, "line": line, "robot_id": f"TRR-{line}", "batch_id": batch["batch_id"],
                "tub_id": f"TUB-{batch['batch_id'][1:]}-{self.rng.integers(1, max(batch['tubs'], 2)):04d}",
                "alarm_code": code, "cleared_after_min": round(float(self.rng.uniform(1, 4) * (2.5 if in_s7 else 1)), 1),
                "scenario_tags": "S7_tyvek_gripper_wear" if in_s7 and code == codes[2] else ""})
        # Filling checks every 30 min, 10 needles
        target = round(batch["fill_volume_ml"] * C.FILL_DENSITY_MG_PER_ML, 1)
        s8 = C.SCENARIOS["S8_filler_needle_underfill"]
        bias_needle = {n: self.rng.normal(0, 1.2) for n in range(1, C.FILLER_NEEDLES + 1)}
        s9 = C.SCENARIOS["S9_vacuum_pump_degradation"]
        t = start
        while t < end:
            dd = day_of(t)
            for nd in range(1, C.FILLER_NEEDLES + 1):
                w = target + bias_needle[nd] + self.rng.normal(0, target * 0.004)
                tag = ""
                if line == "B" and nd == 7 and self.in_window("S8_filler_needle_underfill", dd):
                    w += s8["max_bias_mg"] * (dd - s8["start_day"]) / (s8["fix_day"] - s8["start_day"]) * (target / 1020)
                    tag = "S8_filler_needle_underfill"
                self.t.filling_checks.append({"check_time": t, "line": line, "filler_id": f"FILLER-{line}",
                                              "batch_id": batch["batch_id"], "needle": nd, "fill_weight_mg": round(w, 1),
                                              "target_mg": target, "scenario_tags": tag})
            for st in C.STOPPER_STATIONS:
                vac, sd, tag = self.rng.normal(90, 6), 0.12, ""
                if line == "A" and self.in_window("S9_vacuum_pump_degradation", dd):
                    frac = (dd - s9["start_day"]) / (s9["fix_day"] - s9["start_day"])
                    vac += s9["max_vacuum_rise_mbar"] * frac
                    sd = 0.12 + 0.25 * frac
                    tag = "S9_vacuum_pump_degradation"
                self.t.stopper_checks.append({"check_time": t, "line": line, "station": st, "vacuum_pump": f"VAC-{line}",
                                              "batch_id": batch["batch_id"], "vacuum_mbar_abs": round(vac, 1),
                                              "plunger_depth_mm": round(self.rng.normal(8.0, sd), 3), "scenario_tags": tag})
            t += dt.timedelta(minutes=30)

    # ----------------------------------------------------------- maintenance
    def work_orders(self) -> None:
        wo = 700100
        rng = self.rng
        equipment = (C.CARTS + ["AC-01", "AC-02"] + [f"TRR-{l}" for l in C.LINES]
                     + [f"FILLER-{l}" for l in C.LINES] + [f"VAC-{l}" for l in C.LINES])
        mundane_cm = {
            "FITC": ["Display intermittently blank, reseated cable", "Printer jam on test report printer",
                     "Caster wheel loose, tightened"],
            "AC": ["Door gasket inspection after alarm, no fault found", "Chart recorder pen replaced"],
            "TRR": ["Light curtain realigned", "HMI touch panel recalibrated"],
            "FILLER": ["Needle guard sensor cleaned", "Star wheel lubrication"],
            "VAC": ["Exhaust filter replaced", "Oil level topped up"],
        }

        def add(eq, wtype, day, desc, long_desc, tags=""):
            nonlocal wo
            wo += int(rng.integers(1, 40))
            created = C.START + dt.timedelta(days=day, hours=float(rng.uniform(1, 10)))
            finish = created + dt.timedelta(hours=float(rng.uniform(2, 30)))
            self.t.work_orders.append({"wo_number": wo, "equipment": eq, "work_type": wtype, "created": created,
                                       "actual_finish": finish, "description": desc, "long_description": long_desc,
                                       "scenario_tags": tags})

        for eq in equipment:
            day = float(rng.uniform(5, 40))
            while day < C.DAYS:
                if eq.startswith("FITC"):
                    add(eq, "PMCAL", day, "Quarterly calibration - pressure and flow transducers",
                        "Calibrated pressure transducer and mass flow meter against reference. As found within tolerance.")
                else:
                    add(eq, "PM", day, "Preventive maintenance", "Routine PM checklist completed. No abnormalities.")
                day += float(rng.uniform(55, 75))
            for _ in range(int(rng.integers(0, 3))):
                k = eq.split("-")[0]
                add(eq, "CM", float(rng.uniform(0, C.DAYS)), str(rng.choice(mundane_cm[k])), "Issue resolved on site.")

        s = C.SCENARIOS
        add("FITC-B2", "CM", s["S1_cart_seal_wear"]["fix_day"] - 0.5, "PUPSIT failures - leak check on cart",
            "<p>Leak test on cart found <b>gas leak at inlet manifold</b>. Inlet seal worn and flattened. "
            "Replaced inlet seal kit. Post-repair leak test passed.</p>", "S1_cart_seal_wear")
        add("FITC-B2", "CM", s["S1_cart_seal_wear"]["start_day"] + 8, "Check flow readings trending up",
            "<p>Operator reported higher readings. Visual check OK, no action taken.</p>", "S1_cart_seal_wear")
        add("FITC-C1", "PMCAL", s["S5_sensor_drift"]["fix_day"] - 0.5, "Calibration - flow transducer out of tolerance",
            "<p>As found: flow transducer reading <b>about 30% low</b> vs reference. Adjusted and recalibrated. "
            "As left within tolerance.</p>", "S5_sensor_drift")
        add("AC-02", "CM", s["S4_autoclave_overtemp"]["fix_day"] - 0.5, "Temperature overshoot alarms",
            "<p>Chamber temperature controller overshooting setpoint. Replaced <b>temperature probe</b> and retuned "
            "controller. Verification cycle passed.</p>", "S4_autoclave_overtemp")
        add("TRR-A", "CM", s["S7_tyvek_gripper_wear"]["fix_day"] - 0.5, "Frequent lid removal alarms",
            "<p>Vacuum cups on lid gripper worn and cracked. Replaced all 6 cups.</p>", "S7_tyvek_gripper_wear")
        add("FILLER-B", "CM", s["S8_filler_needle_underfill"]["fix_day"] - 0.5, "Needle 7 low fill weights",
            "<p>Dosing pump 7 piston seal worn. Replaced piston and seal. Gravimetric check passed.</p>",
            "S8_filler_needle_underfill")
        add("VAC-A", "PM", s["S9_vacuum_pump_degradation"]["fix_day"] - 0.5, "Vacuum pump service",
            "<p>Pump vanes worn, ultimate vacuum degraded. Replaced vanes and oil. Ultimate vacuum restored.</p>",
            "S9_vacuum_pump_degradation")

    # ----------------------------------------------------------- orchestration
    def run(self) -> Truth:
        end_time = C.START + dt.timedelta(days=C.DAYS)
        s1 = C.SCENARIOS["S1_cart_seal_wear"]
        self.s1_start_index = None
        for line in C.LINES:
            t = C.START + dt.timedelta(hours=float(self.rng.uniform(0, 6)))
            prev_end = t - dt.timedelta(hours=8)
            while t < end_time - dt.timedelta(days=2):
                d = day_of(t)
                shut = [w for w in C.PLANNED_SHUTDOWNS.get(line, []) if w[0] <= d < w[1]]
                if shut:
                    t = C.START + dt.timedelta(days=shut[0][1], hours=float(self.rng.uniform(0, 4)))
                    continue
                if line == "B" and self.s1_start_index is None and d >= s1["start_day"]:
                    self.s1_start_index = self.cart_assembly_count["FITC-B2"]
                end = self.simulate_batch(line, t, prev_end)
                prev_end = end
                t = end + dt.timedelta(hours=float(self.rng.uniform(5, 10)))
        # environment hourly
        h = C.START
        while h < end_time:
            for line in C.LINES:
                self.t.environment.append({"timestamp": h, "line": line, "room_temp_c": self.room_temp(line, h),
                                           "rel_humidity_pct": round(float(self.rng.normal(42, 3)), 1)})
            h += H
        self.work_orders()
        return self.t


def PRODUCT_PICK(rng, line):
    options = C.PRODUCTS[line]
    p, v = options[int(rng.integers(0, len(options)))]
    return p, v
