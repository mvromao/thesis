"""Stage 2: join the extracted artefacts into the tables the Results chapter needs.

    python -m pipeline.build_tables

Reads `extracted/` (stage 1) plus the iperf3 exports and ping captures, writes
`data_v2/`. Never touches a raw stack log.

The join that matters is Rounds 2-3: one gNB log covers a whole location
session of ~12 repetitions, so each repetition's radio KPIs come from the
`[METRICS ]` rows whose timestamp falls inside that repetition's iperf3 window.

Clock handling, verified rather than assumed: gNB log timestamps are UTC. The
CellularLab banner (`[18:39:55]`) is local time (UTC+1) while the `Time:` line
in the same record reads `17:39:55 UTC`, and the gNB log's own first line for
that session is `17:39:30`. The join therefore uses the `Time:` line and never
the banner.
"""
from __future__ import annotations

import csv
import gzip
import json
import statistics as st
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from . import paths, iperf, console

RAMP_S = 5.0        # discard TCP ramp-up
TEST_S = 20.0       # iperf3 -t 20

# radio KPIs averaged over each repetition's window
UE_KPIS = ["pusch_snr_db", "pusch_rsrp_db", "last_phr_db", "ul_mcs", "dl_mcs",
           "ul_error_rate", "dl_error_rate", "ul_nof_prbs", "dl_nof_prbs",
           "ul_brate_bps", "dl_brate_bps", "cqi", "dl_bs_bytes", "bsr_bytes",
           "ta_ns", "avg_sr_to_pusch_delay_ms"]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _mean(vals):
    v = [x for x in vals if x is not None]
    return round(st.fmean(v), 4) if v else None


def _read_csv_gz(path):
    if not path.exists():
        return []
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _naive_utc(ts):
    """gNB log stamps are UTC but written without an offset."""
    return datetime.fromisoformat(ts)


def load_metrics(unit_id, name="metrics_ue.csv.gz"):
    rows = _read_csv_gz(paths.EXTRACTED / unit_id / name)
    for r in rows:
        try:
            r["_t"] = _naive_utc(r["ts"])
        except (ValueError, KeyError):
            r["_t"] = None
    return [r for r in rows if r["_t"]]


def _prb_per_tx(rows):
    """Instantaneous grant width, and the PHR residual it lets you compute.

    `ul_nof_prbs` is a *cumulative* count over the 1 s reporting period, not the
    grant size -- it runs to tens of thousands in a 51-PRB cell. Dividing by the
    transmission count recovers the per-transmission allocation M_RB, which is
    what the PHR open-loop formula's `10*log10(M_RB)` term refers to.

    `phr_residual_db = last_phr_db + 10*log10(M_RB)` removes that term, leaving
    `P_CMAX - P_O - alpha*PL` -- the link-budget quantity that is actually
    comparable between locations. Without this, a wider grant looks like worse
    radio conditions.
    """
    import math
    out = {}
    for d in ("ul", "dl"):
        per = []
        for r in rows:
            prbs = _f(r.get(f"{d}_nof_prbs"))
            n = (_f(r.get(f"{d}_nof_ok")) or 0) + (_f(r.get(f"{d}_nof_nok")) or 0)
            if prbs and n > 0:
                per.append(prbs / n)
        out[f"{d}_prbs_per_tx"] = _mean(per)
    res = []
    for r in rows:
        phr = _f(r.get("last_phr_db"))
        prbs = _f(r.get("ul_nof_prbs"))
        n = (_f(r.get("ul_nof_ok")) or 0) + (_f(r.get("ul_nof_nok")) or 0)
        if phr is not None and prbs and n > 0:
            res.append(phr + 10 * math.log10(max(prbs / n, 1.0)))
    out["phr_residual_db"] = _mean(res)
    return out


def window_rows(rows, start_utc, ramp=RAMP_S, dur=TEST_S):
    """[METRICS ] rows inside one repetition's steady-state window."""
    s = start_utc.replace(tzinfo=None) + timedelta(seconds=ramp)
    e = start_utc.replace(tzinfo=None) + timedelta(seconds=dur)
    return [r for r in rows if s <= r["_t"] <= e]


# ---------------------------------------------------------------------------

def build_reps():
    """One row per iperf3 repetition: throughput plus windowed radio KPIs."""
    out, cache = [], {}
    for rep in paths.reps():
        unit = {u.unit_id: u for u in paths.log_units()}[rep.unit_id]
        cfg = unit.config
        row = {
            "rep_id": rep.rep_id, "unit_id": rep.unit_id, "round": rep.round,
            "campaign": paths.CAMPAIGN[rep.round], "tech": rep.tech,
            "location": rep.location, "distance_m": rep.distance_m,
            "protocol": rep.protocol, "direction": rep.direction, "rep": rep.rep,
            "variant": rep.variant or "",
            "rx_gain": cfg.rx_gain, "tx_gain": cfg.tx_gain, "tdd": cfg.tdd_pattern,
        }

        if rep.round == 1:
            # no [METRICS ]; per-second KPIs come from the console table, and
            # throughput is the mean over the active stretch of that table
            rows = console.active(console.parse(rep.console_log, rep.tech),
                                  rep.direction) if rep.console_log else []
            key = "dl_brate_bps" if rep.direction == "DL" else "ul_brate_bps"
            thr = _mean([_f(r.get(key)) for r in rows])
            row.update(
                throughput_Mbps=round(thr / 1e6, 3) if thr else None,
                throughput_src="console trace (sequence-aligned)",
                n_samples=len(rows),
                pusch_snr_db=_mean([_f(r.get("ul_sinr_db")) for r in rows]),
                last_phr_db=_mean([_f(r.get("phr_db")) for r in rows]),
                ul_mcs=_mean([_f(r.get("ul_mcs")) for r in rows]),
                dl_mcs=_mean([_f(r.get("dl_mcs")) for r in rows]),
                ul_error_rate=_mean([_f(r.get("ul_bler")) for r in rows]),
                dl_error_rate=_mean([_f(r.get("dl_bler")) for r in rows]),
                pusch_rsrp_db=_mean([_f(r.get("ul_rsrp_db")) for r in rows]),
                time_aligned=0,
            )
        else:
            d = iperf.parse_export(rep.client_export, rep.iteration) or {}
            row.update(
                throughput_Mbps=d.get("throughput_Mbps"),
                throughput_src=d.get("throughput_src"),
                sender_Mbps=d.get("sender_Mbps"), receiver_Mbps=d.get("receiver_Mbps"),
                mean_Mbps_5s_on=d.get("mean_Mbps_5s_on"),
                min_Mbps=d.get("min_Mbps"), max_Mbps=d.get("max_Mbps"),
                receiver_stalled=d.get("receiver_stalled"),
                jitter_ms=d.get("jitter_ms"), loss_pct=d.get("loss_pct"),
                loss_is_meaningful=d.get("loss_is_meaningful"),
                start_utc=d.get("start_utc"), time_aligned=1,
            )
            if rep.unit_id not in cache:
                cache[rep.unit_id] = load_metrics(rep.unit_id)
            if d.get("start_utc"):
                w = window_rows(cache[rep.unit_id],
                                datetime.fromisoformat(d["start_utc"]))
                row["n_samples"] = len(w)
                row["rsrp_ovl_share"] = round(
                    sum(int(_f(r.get("rsrp_ovl")) or 0) for r in w) / len(w), 4) if w else None
                for k in UE_KPIS:
                    row[k] = _mean([_f(r.get(k)) for r in w])
                row.update(_prb_per_tx(w))
        out.append(row)
    return out


def build_throughput_summary(reps):
    """Aggregate repetitions into the comparison cells the chapter is built on."""
    groups = defaultdict(list)
    for r in reps:
        groups[(r["round"], r["tech"], r["location"], r["distance_m"],
                r["protocol"], r["direction"], r["variant"])].append(r)
    out = []
    for k, rows in sorted(groups.items()):
        thr = [r["throughput_Mbps"] for r in rows if r["throughput_Mbps"] is not None]
        rec = dict(zip(("round", "tech", "location", "distance_m", "protocol",
                        "direction", "variant"), k))
        rec.update(
            n=len(rows), n_valid=len(thr),
            mean_Mbps=round(st.fmean(thr), 3) if thr else None,
            sd_Mbps=round(st.stdev(thr), 3) if len(thr) > 1 else None,
            min_Mbps=min(thr) if thr else None, max_Mbps=max(thr) if thr else None,
            rx_gain=rows[0].get("rx_gain"), tdd=rows[0].get("tdd"),
        )
        for k2 in ("pusch_snr_db", "last_phr_db", "ul_mcs", "ul_error_rate",
                   "dl_error_rate", "rsrp_ovl_share"):
            rec[k2] = _mean([r.get(k2) for r in rows])
        out.append(rec)
    return out


def build_census():
    rows = []
    for u in paths.log_units():
        p = paths.EXTRACTED / u.unit_id / "census.json"
        if not p.exists():
            continue
        c = json.loads(p.read_text(encoding="utf-8"))
        by_layer = c.get("bytes_by_layer", {})
        tot = c.get("bytes_total") or 1
        rows.append({
            "unit_id": c["unit_id"], "round": c["round"], "tech": c["tech"],
            "location": c["location"], "duration_s": c.get("duration_s"),
            "log_bytes": c.get("log_bytes"), "lines_total": c.get("lines_total"),
            "bytes_per_s": round(c["bytes_per_s"], 1) if c.get("bytes_per_s") else None,
            "gb_per_hour": round(c["gb_per_hour"], 3) if c.get("gb_per_hour") else None,
            "metrics_lines": c.get("metrics_lines"),
            "metrics_line_share": c.get("metrics_line_share"),
            "hexdump_byte_share": round(c.get("continuation_byte_share") or 0, 5),
            **{f"share_{k}": round(v / tot, 4) for k, v in list(by_layer.items())[:6]},
        })
    return rows


def build_phy():
    rows = []
    for u in paths.log_units():
        p = paths.EXTRACTED / u.unit_id / "phy_summary.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        for ch in ("PUSCH", "PDSCH"):
            v = d.get(ch)
            if not v:
                continue
            mod = v.get("mod_hist", {})
            n_mod = sum(mod.values()) or 1
            rows.append({
                "unit_id": u.unit_id, "round": u.round, "tech": u.tech,
                "location": u.location, "distance_m": u.distance_m,
                "variant": u.variant, "channel": ch, "n": v["n"],
                "bler_first_tx": round(v["bler_first_tx"], 5) if v.get("bler_first_tx") is not None else None,
                "rv0_share": round(v["rv0_share"], 5) if v.get("rv0_share") is not None else None,
                "share_256QAM": round(mod.get("256QAM", 0) / n_mod, 4),
                "share_64QAM": round(mod.get("64QAM", 0) / n_mod, 4),
                "share_QPSK": round(mod.get("QPSK", 0) / n_mod, 4),
                "sinr_p50": v["sinr_db"].get("p50"), "sinr_p5": v["sinr_db"].get("p5"),
                "prb_p50": v["prb_width"].get("p50"), "prb_max": v["prb_width"].get("max"),
                "proc_us_p50": v["proc_time_us"].get("p50"),
                "proc_us_p99": v["proc_time_us"].get("p99"),
                "proc_us_max": v["proc_time_us"].get("max"),
            })
    return rows


def build_events():
    rows = []
    for u in paths.log_units():
        p = paths.EXTRACTED / u.unit_id / "census.json"
        if not p.exists():
            continue
        c = json.loads(p.read_text(encoding="utf-8"))
        ev = c.get("event_counts", {})
        rows.append({
            "unit_id": u.unit_id, "round": u.round, "tech": u.tech,
            "location": u.location, "distance_m": u.distance_m,
            "warnings": c.get("lines_by_level", {}).get("W", 0),
            "errors": c.get("lines_by_level", {}).get("E", 0),
            **{k: ev.get(k, 0) for k in
               ("rlf", "reest", "release", "rach", "phy_dl_late", "phy_ul_late",
                "phy_rt_failure", "rf_underflow", "rf_overflow", "harq_maxretx",
                "sched_err_ind")},
        })
    return rows


def build_tdd_airtime():
    """Per-slot-index PRB usage -- the TDD airtime argument, measured.

    `pusch_rbs_per_tdd_slot_idx` reports resource-block usage per slot position
    within the TDD period, so the uplink ceiling can be read straight off the
    pattern instead of inferred from grant counts.
    """
    rows = []
    for u in paths.log_units():
        cells = _read_csv_gz(paths.EXTRACTED / u.unit_id / "metrics_cell.csv.gz")
        if not cells:
            continue
        busy = [c for c in cells if (_f(c.get("total_ul_brate_bps")) or 0) > 1e5
                or (_f(c.get("total_dl_brate_bps")) or 0) > 1e5]
        if not busy:
            continue
        n_slots = 0
        ul_acc, dl_acc = defaultdict(list), defaultdict(list)
        for c in busy:
            for tag, acc in (("pusch_rbs_per_tdd_slot_idx", ul_acc),
                             ("pdsch_rbs_per_tdd_slot_idx", dl_acc)):
                parts = [p for p in (c.get(tag) or "").split("|") if p != ""]
                n_slots = max(n_slots, len(parts))
                for i, p in enumerate(parts):
                    if (v := _f(p)) is not None:
                        acc[i].append(v)
        cfg = u.config
        rec = {"unit_id": u.unit_id, "round": u.round, "location": u.location,
               "distance_m": u.distance_m, "variant": u.variant,
               "tdd": cfg.tdd_pattern, "rx_gain": cfg.rx_gain,
               "ul_slot_fraction_cfg": round(cfg.ul_slot_fraction, 4) if cfg.ul_slot_fraction else None,
               "n_busy_samples": len(busy)}
        for i in range(n_slots):
            rec[f"pusch_rb_slot{i}"] = _mean(ul_acc.get(i, []))
            rec[f"pdsch_rb_slot{i}"] = _mean(dl_acc.get(i, []))
        tot_ul = sum(v for i in range(n_slots) if (v := rec[f"pusch_rb_slot{i}"]))
        tot_dl = sum(v for i in range(n_slots) if (v := rec[f"pdsch_rb_slot{i}"]))
        rec["ul_rb_share_measured"] = round(tot_ul / (tot_ul + tot_dl), 4) if (tot_ul + tot_dl) else None
        rec["mean_ul_brate_Mbps"] = _mean([(_f(c.get("total_ul_brate_bps")) or 0) / 1e6 for c in busy])
        rec["mean_dl_brate_Mbps"] = _mean([(_f(c.get("total_dl_brate_bps")) or 0) / 1e6 for c in busy])
        rec["late_ul_harqs"] = sum(int(_f(c.get("late_ul_harqs")) or 0) for c in cells)
        rec["late_dl_harqs"] = sum(int(_f(c.get("late_dl_harqs")) or 0) for c in cells)
        rows.append(rec)
    return rows


def build_realtime():
    """MAC slot timing against the 500 us slot deadline (5G only)."""
    rows = []
    for u in paths.log_units():
        macs = _read_csv_gz(paths.EXTRACTED / u.unit_id / "metrics_mac.csv.gz")
        if not macs:
            continue
        def col(c):
            return [v for m in macs if (v := _f(m.get(c))) is not None]
        budget = _mean(col("slot_duration_us")) or 500.0
        wmax = col("wall_clock_latency_max_us")
        rows.append({
            "unit_id": u.unit_id, "round": u.round, "location": u.location,
            "distance_m": u.distance_m, "variant": u.variant,
            "slot_budget_us": budget, "n_reports": len(macs),
            "wall_clock_avg_us": _mean(col("wall_clock_latency_avg_us")),
            "wall_clock_max_us": max(wmax) if wmax else None,
            "reports_over_budget": sum(1 for v in wmax if v > budget),
            "share_over_budget": round(sum(1 for v in wmax if v > budget) / len(wmax), 4) if wmax else None,
            "sched_latency_avg_us": _mean(col("sched_latency_avg_us")),
            "slot_ind_msg_time_diff_avg_us": _mean(col("slot_ind_msg_time_diff_avg_us")),
            "involuntary_ctx_switches": sum(int(v) for v in col("involuntary_ctx_switches")),
        })
    return rows


def build_ping():
    series, summary = [], []
    for loc, p in paths.ping_captures().items():
        rows, s = iperf.parse_ping(p)
        s["location"] = loc
        s["distance_m"] = {"A": 2, "B": 6, "C": 10}[loc]
        summary.append(s)
        for r in rows:
            series.append({"location": loc, **r})
    return series, summary


def _write(name, rows, cols=None):
    if not rows:
        print(f"  (skip {name}: no rows)")
        return
    paths.DATA_V2.mkdir(parents=True, exist_ok=True)
    if cols is None:
        cols, seen = [], set()
        for r in rows:
            for k in r:
                if k not in seen and not k.startswith("_"):
                    seen.add(k); cols.append(k)
    path = paths.DATA_V2 / name
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)
    except PermissionError:
        # Excel takes an exclusive lock on an open workbook, which is easy to
        # hit while browsing these tables. Say so instead of dumping a traceback.
        print(f"  {name:28s} SKIPPED - file is locked (close it in Excel and re-run)")
        return
    print(f"  {name:28s} {len(rows):5d} rows")


def main():
    print("building data_v2/ ...")
    reps = build_reps()
    _write("reps.csv", reps)
    _write("throughput_summary.csv", build_throughput_summary(reps))
    _write("logging_cost.csv", build_census())
    _write("phy_by_unit.csv", build_phy())
    _write("events_by_unit.csv", build_events())
    _write("tdd_airtime.csv", build_tdd_airtime())
    _write("realtime.csv", build_realtime())
    series, summary = build_ping()
    _write("ping_series.csv", series)
    _write("ping_summary.csv", summary)
    print(f"-> {paths.DATA_V2}")


if __name__ == "__main__":
    main()
