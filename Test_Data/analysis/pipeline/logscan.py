"""Stage 1: one streaming pass over a stack log.

Everything downstream reads the compact outputs written here, never the raw
logs again. That is the point: `[METRICS ]` lines are 0.025 % of a gNB log
(126 lines in 500 000 in `3 - 03-Aug/Location1/gnb1.log`), so separating them
turns a 700 MB file into a few hundred kilobytes and makes the rest of the
analysis interactive instead of an overnight job.

Per log unit it writes:

    metrics_ue.csv.gz     [METRICS ] Scheduler UE   -- per-UE radio KPIs, 1 Hz
    metrics_cell.csv.gz   [METRICS ] Scheduler cell -- cell totals, slot/PRB use
    metrics_mac.csv.gz    [METRICS ] MAC cell       -- slot timing vs deadline
    events.csv.gz         every WARNING/ERROR line, classified
    phy_summary.json      per-transmission PUSCH/PDSCH aggregates
    census.json           what the other 99.97 % of the file consists of

The census is not bookkeeping: the logging-cost result (bytes/s of a
permanently-running base station, and the share of it that is hex dumps) is
exactly this table, and it previously existed for Round 1 only.
"""
from __future__ import annotations

import gzip
import csv
import json
import re
from array import array
from collections import Counter
from datetime import datetime

from . import units
from .units import val, parse_metrics_body

TS_LEN = 26  # "2026-08-03T17:39:52.828231"

# ---------------------------------------------------------------------------
# output schemas -- explicit so the CSV header is stable across runs
# ---------------------------------------------------------------------------

# name in log -> (column name, transform)
# Values are parsed to base SI units and scaled back out to the unit named in
# the column, so they round-trip through float; `_r` clears the resulting noise
# (132ns -> 1.32e-07 -> 132.00000000000003) that would otherwise land in the CSV.
def _r(v, scale=1.0):
    return None if v is None else round(v * scale, 6)


_MS = lambda v: _r(v, 1e3)                              # noqa: E731  seconds -> ms
_US = lambda v: _r(v, 1e6)                              # noqa: E731  seconds -> us
_NS = lambda v: _r(v, 1e9)                              # noqa: E731  seconds -> ns
_ID = lambda v: _r(v)                                   # noqa: E731

UE_FIELDS = [
    ("ue", "ue", _ID), ("rnti", "rnti", None), ("pci", "pci", _ID),
    ("cqi", "cqi", _ID), ("dl_ri", "dl_ri", _ID), ("dl_mcs", "dl_mcs", _ID),
    ("dl_brate", "dl_brate_bps", _ID), ("dl_nof_ok", "dl_nof_ok", _ID),
    ("dl_nof_nok", "dl_nof_nok", _ID), ("dl_error_rate", "dl_error_rate", _ID),
    ("dl_bs", "dl_bs_bytes", _ID), ("dl_nof_prbs", "dl_nof_prbs", _ID),
    ("dl_olla", "dl_olla", _ID),
    ("pusch_snr_db", "pusch_snr_db", _ID), ("pusch_rsrp_db", "pusch_rsrp_db", _ID),
    ("ul_ri", "ul_ri", _ID), ("ul_mcs", "ul_mcs", _ID),
    ("ul_brate", "ul_brate_bps", _ID), ("ul_nof_ok", "ul_nof_ok", _ID),
    ("ul_nof_nok", "ul_nof_nok", _ID), ("ul_error_rate", "ul_error_rate", _ID),
    ("ul_nof_prbs", "ul_nof_prbs", _ID), ("ul_olla", "ul_olla", _ID),
    ("bsr", "bsr_bytes", _ID), ("sr_count", "sr_count", _ID),
    ("ta", "ta_ns", _NS), ("last_phr", "last_phr_db", _ID),
    ("pusch_invalid_harqs", "pusch_invalid_harqs", _ID),
    ("pusch_invalid_csis", "pusch_invalid_csis", _ID),
    ("f0f1_invalid_harqs", "f0f1_invalid_harqs", _ID),
    ("f2f3f4_invalid_harqs", "f2f3f4_invalid_harqs", _ID),
    ("max_pdsch_distance", "max_pdsch_distance_ms", _MS),
    ("max_pusch_distance", "max_pusch_distance_ms", _MS),
    ("avg_crc_delay", "avg_crc_delay_ms", _MS),
    ("avg_sr_to_pusch_delay", "avg_sr_to_pusch_delay_ms", _MS),
    ("max_sr_to_pusch_delay", "max_sr_to_pusch_delay_ms", _MS),
    ("avg_pucch_harq_delay", "avg_pucch_harq_delay_ms", _MS),
    ("max_dl_lcid1_flush_delay", "max_dl_lcid1_flush_delay_ms", _MS),
]

CELL_FIELDS = [
    ("pci", "pci", _ID),
    ("total_dl_brate", "total_dl_brate_bps", _ID),
    ("total_ul_brate", "total_ul_brate_bps", _ID),
    ("nof_prbs", "nof_prbs", _ID),
    ("nof_dl_slots", "nof_dl_slots", _ID), ("nof_ul_slots", "nof_ul_slots", _ID),
    ("nof_prach_preambles", "nof_prach_preambles", _ID),
    ("error_indications", "error_indications", _ID),
    ("pdsch_rbs_per_slot", "pdsch_rbs_per_slot", _ID),
    ("pusch_rbs_per_slot", "pusch_rbs_per_slot", _ID),
    ("pdschs_per_slot", "pdschs_per_slot", _ID),
    ("puschs_per_slot", "puschs_per_slot", _ID),
    ("failed_dl_pdcch", "failed_dl_pdcch", _ID),
    ("failed_ul_pdcch", "failed_ul_pdcch", _ID),
    ("failed_uci", "failed_uci", _ID), ("nof_ues", "nof_ues", _ID),
    ("mean_latency", "mean_latency_us", _US), ("max_latency", "max_latency_us", _US),
    ("msg3_ok", "msg3_ok", _ID), ("msg3_nok", "msg3_nok", _ID),
    ("conres_timer_expired", "conres_timer_expired", _ID),
    ("late_dl_harqs", "late_dl_harqs", _ID), ("late_ul_harqs", "late_ul_harqs", _ID),
    ("pucch_tot_rb_usage_avg", "pucch_tot_rb_usage_avg", _ID),
    ("avg_prach_delay", "avg_prach_delay", _ID),
]
# kept as pipe-joined arrays, not scalars -- the per-slot-index structure IS the
# TDD airtime evidence and must survive into the CSV
CELL_ARRAYS = ["pusch_rbs_per_tdd_slot_idx", "pdsch_rbs_per_tdd_slot_idx"]

MAC_FIELDS = [
    ("nof_slots", "nof_slots", _ID),
    ("slot_duration", "slot_duration_us", _US),
    ("nof_voluntary_context_switches", "voluntary_ctx_switches", _ID),
    ("nof_involuntary_context_switches", "involuntary_ctx_switches", _ID),
    ("wall_clock_latency_avg", "wall_clock_latency_avg_us", _US),
    ("wall_clock_latency_max", "wall_clock_latency_max_us", _US),
    ("sched_latency_avg", "sched_latency_avg_us", _US),
    ("sched_latency_max", "sched_latency_max_us", _US),
    ("dl_tti_req_latency_avg", "dl_tti_req_latency_avg_us", _US),
    ("dl_tti_req_latency_max", "dl_tti_req_latency_max_us", _US),
    ("tx_data_req_latency_avg", "tx_data_req_latency_avg_us", _US),
    ("ul_tti_req_latency_avg", "ul_tti_req_latency_avg_us", _US),
    ("slot_ind_dequeue_latency_avg", "slot_ind_dequeue_latency_avg_us", _US),
    ("slot_ind_dequeue_latency_max", "slot_ind_dequeue_latency_max_us", _US),
    ("slot_ind_msg_time_diff_avg", "slot_ind_msg_time_diff_avg_us", _US),
    ("slot_ind_msg_time_diff_max", "slot_ind_msg_time_diff_max_us", _US),
]

# ---------------------------------------------------------------------------
# event classification -- table inherited verbatim from scripts/scan_events.py
# ---------------------------------------------------------------------------

EVENTS = {
    "phy_dl_late":     re.compile(r"Downlink data late"),
    "phy_ul_late":     re.compile(r"Uplink data late|Late uplink"),
    "phy_rt_failure":  re.compile(r"Real-time failure in lower PHY"),
    "fapi_late":       re.compile(r"Real-time failure in FAPI"),
    "modulator_busy":  re.compile(r"modulator is busy"),
    "rlf":             re.compile(r"RLF detected|[Rr]adio link failure"),
    "sched_err_ind":   re.compile(r"Discarding error indication"),
    "rf_overflow":     re.compile(r"\bOverflow\b"),
    "rf_underflow":    re.compile(r"\bUnderflow\b|\bUnderrun\b"),
    "rf_late":         re.compile(r"\bLate\b"),
    "harq_maxretx":    re.compile(r"max.?retx|[Mm]aximum number of retransmissions|max consecutive HARQ"),
    "rlc_drop":        re.compile(r"[Dd]iscard|[Dd]ropp"),
    "rach":            re.compile(r"\bPRACH\b|\bRACH\b|RandomAccess"),
    "reest":           re.compile(r"[Rr]eestablish"),
    "release":         re.compile(r"UEContextRelease|Releasing ue|ue release"),
}
# normalise varying numbers out of a message so templates group together
_NUMS = re.compile(r"[-+]?\d+\.?\d*")


class _PhyAcc:
    """Per-channel accumulator. `array('d')` keeps a million samples in 8 MB."""

    __slots__ = ("n", "crc_ok", "crc_ko", "rv", "mod", "sinr", "prb", "tproc", "tbs")

    def __init__(self):
        self.n = 0
        self.crc_ok = self.crc_ko = 0
        self.rv = Counter()
        self.mod = Counter()
        self.sinr = array("d")
        self.prb = array("d")
        self.tproc = array("d")
        self.tbs = array("d")

    def summary(self):
        def pct(a, ps=(1, 5, 25, 50, 75, 95, 99, 99.9)):
            if not a:
                return {}
            s = sorted(a)
            out = {"n": len(s), "mean": round(sum(s) / len(s), 4),
                   "min": round(s[0], 4), "max": round(s[-1], 4)}
            for p in ps:
                k = min(len(s) - 1, int(round((p / 100) * (len(s) - 1))))
                out[f"p{p}"] = round(s[k], 4)
            return out

        tot = self.crc_ok + self.crc_ko
        return {
            "n": self.n,
            "crc_ok": self.crc_ok, "crc_ko": self.crc_ko,
            "bler_first_tx": (self.crc_ko / tot) if tot else None,
            "rv_hist": dict(self.rv),
            "rv0_share": (self.rv.get(0, 0) / sum(self.rv.values())) if self.rv else None,
            "mod_hist": dict(self.mod),
            "sinr_db": pct(self.sinr),
            "prb_width": pct(self.prb),
            "proc_time_us": pct(self.tproc),
            "tbs_bytes": pct(self.tbs),
        }


def _open_out(path):
    return gzip.open(path, "wt", newline="", encoding="utf-8", compresslevel=6)


def scan(unit, max_lines=None):
    """Stream one LogUnit's stack log and write its extracted artefacts."""
    out = unit.out_dir
    out.mkdir(parents=True, exist_ok=True)
    log = unit.stack_log

    ue_cols = ["ts", "t_rel_s", "rsrp_ovl"] + [c for _, c, _ in UE_FIELDS]
    cell_cols = ["ts", "t_rel_s"] + [c for _, c, _ in CELL_FIELDS] + CELL_ARRAYS
    mac_cols = ["ts", "t_rel_s"] + [c for _, c, _ in MAC_FIELDS]

    census_layer = Counter()
    census_layer_bytes = Counter()
    census_level = Counter()
    event_counts = Counter()
    templates = Counter()
    phy = {"PUSCH": _PhyAcc(), "PDSCH": _PhyAcc(), "PUCCH": _PhyAcc(), "PDCCH": _PhyAcc()}
    # (channel, second, modulation) -> count. The per-run histograms in
    # phy_summary.json show the modulation *mix*; this shows the modulation
    # *ladder* -- link adaptation stepping up and down over time. Taken from the
    # PHY `mod=` field, which states the modulation outright, rather than from
    # the MCS index, whose meaning depends on the configured MCS table.
    mod_sec = Counter()

    n_lines = n_bytes = 0
    n_cont = 0           # hex-dump / continuation lines
    n_cont_bytes = 0
    n_metrics = 0
    n_rsrp_ovl = 0
    t0 = None
    ts_first = ts_last = None

    f_ue = _open_out(out / "metrics_ue.csv.gz")
    f_cell = _open_out(out / "metrics_cell.csv.gz")
    f_mac = _open_out(out / "metrics_mac.csv.gz")
    f_ev = _open_out(out / "events.csv.gz")
    w_ue = csv.DictWriter(f_ue, fieldnames=ue_cols, extrasaction="ignore")
    w_cell = csv.DictWriter(f_cell, fieldnames=cell_cols, extrasaction="ignore")
    w_mac = csv.DictWriter(f_mac, fieldnames=mac_cols, extrasaction="ignore")
    w_ev = csv.writer(f_ev)
    w_ue.writeheader(); w_cell.writeheader(); w_mac.writeheader()
    w_ev.writerow(["ts", "t_rel_s", "layer", "level", "classes", "message"])

    try:
        with open(log, encoding="utf-8", errors="ignore", buffering=1 << 20) as fh:
            for line in fh:
                n_lines += 1
                n_bytes += len(line)
                if max_lines and n_lines > max_lines:
                    break

                c0 = line[0]
                if c0 < "0" or c0 > "9":
                    # hex dump body, YAML config dump, or console table -- all
                    # continuation of the previous record
                    n_cont += 1
                    n_cont_bytes += len(line)
                    continue

                close = line.find("] ", TS_LEN)
                if close < 0:
                    n_cont += 1
                    continue
                ts = line[:TS_LEN]
                layer = line[TS_LEN + 2:close].rstrip()
                rest = line[close + 2:]

                if rest[:1] == "[" and rest[2:3] == "]":
                    level = rest[1]
                    body = rest[4:]
                else:
                    level = ""            # [METRICS ] carries no level marker
                    body = rest

                census_layer[layer] += 1
                census_layer_bytes[layer] += len(line)
                census_level[level or "M"] += 1

                if ts_first is None:
                    ts_first = ts
                ts_last = ts
                if t0 is None:
                    try:
                        t0 = datetime.fromisoformat(ts)
                    except ValueError:
                        t0 = None
                t_rel = ""
                if t0 is not None:
                    try:
                        t_rel = round((datetime.fromisoformat(ts) - t0).total_seconds(), 6)
                    except ValueError:
                        t_rel = ""

                # ---- the needle: [METRICS ] ---------------------------------
                if layer == "METRICS":
                    n_metrics += 1
                    if body.startswith("Scheduler UE"):
                        kv = parse_metrics_body(body)
                        ovl = units.is_overload(kv.get("pusch_rsrp_db"))
                        n_rsrp_ovl += ovl
                        row = {"ts": ts, "t_rel_s": t_rel, "rsrp_ovl": int(ovl)}
                        for src, col, tf in UE_FIELDS:
                            raw = kv.get(src)
                            row[col] = raw if tf is None else tf(val(raw))
                        w_ue.writerow(row)
                    elif body.startswith("Scheduler cell"):
                        kv = parse_metrics_body(body)
                        row = {"ts": ts, "t_rel_s": t_rel}
                        for src, col, tf in CELL_FIELDS:
                            row[col] = tf(val(kv.get(src)))
                        for a in CELL_ARRAYS:
                            row[a] = kv.get(a, "")
                        w_cell.writerow(row)
                    elif body.startswith("MAC cell"):
                        kv = parse_metrics_body(body)
                        row = {"ts": ts, "t_rel_s": t_rel}
                        for src, col, tf in MAC_FIELDS:
                            row[col] = tf(val(kv.get(src)))
                        w_mac.writerow(row)
                    continue

                # ---- per-transmission PHY ------------------------------------
                if layer.startswith("PHY") or layer.startswith("MAC"):
                    for ch in ("PUSCH:", "PDSCH:"):
                        i = body.find(ch)
                        if i < 0:
                            continue
                        acc = phy[ch[:-1]]
                        acc.n += 1
                        kv = units.kv_pairs(body[i + len(ch):])
                        crc = kv.get("crc")
                        if crc == "OK":
                            acc.crc_ok += 1
                        elif crc == "KO":
                            acc.crc_ko += 1
                        rv = val(kv.get("rv", "").strip("{}"))
                        if rv is not None:
                            acc.rv[int(rv)] += 1
                        if (mod := units.mod_name(kv.get("mod"))):
                            acc.mod[mod] += 1
                            mod_sec[(ch[:-1], ts[:19], mod)] += 1
                        # 5G calls it `sinr`, 4G `snr`
                        if (v := val(kv.get("sinr", kv.get("snr")))) is not None:
                            acc.sinr.append(v)
                        if (v := val(kv.get("t"))) is not None:
                            acc.tproc.append(v * 1e6)          # seconds -> us
                        if (v := val(kv.get("tbs", "").strip("{}"))) is not None:
                            acc.tbs.append(v)
                        # 5G prints the allocation as a range `prb=[26, 43)`,
                        # 4G as `rb=(2,46)` or a plain count `nof_prb=3`;
                        # val() collapses a range to its width.
                        p = kv.get("prb") or kv.get("rb")
                        if p is not None:
                            if (v := val(p)) is not None:
                                acc.prb.append(v)
                        elif (v := val(kv.get("nof_prb"))) is not None:
                            acc.prb.append(v)
                        break

                # ---- warnings and errors ------------------------------------
                if level in ("W", "E"):
                    msg = body.strip()
                    hits = [name for name, rx in EVENTS.items() if rx.search(msg)]
                    for h in hits:
                        event_counts[h] += 1
                    templates[_NUMS.sub("#", msg)[:160]] += 1
                    w_ev.writerow([ts, t_rel, layer, level, "|".join(hits), msg[:300]])
    finally:
        for f in (f_ue, f_cell, f_mac, f_ev):
            f.close()

    # modulation ladder: one row per second per channel
    if mod_sec:
        ladder = ["QPSK", "16QAM", "64QAM", "256QAM"]
        keys = sorted({(c, s) for c, s, _ in mod_sec})
        t_zero = datetime.fromisoformat(ts_first) if ts_first else None
        with _open_out(out / "mod_series.csv.gz") as f:
            w = csv.writer(f)
            w.writerow(["ts", "t_rel_s", "channel", *ladder, "total",
                        "share_256QAM", "mean_bits_per_symbol"])
            for ch, sec in keys:
                counts = [mod_sec[(ch, sec, m)] for m in ladder]
                other = sum(v for (c, s, m), v in mod_sec.items()
                            if c == ch and s == sec and m not in ladder)
                tot = sum(counts) + other
                bits = {"QPSK": 2, "16QAM": 4, "64QAM": 6, "256QAM": 8}
                mbps = sum(counts[i] * bits[m] for i, m in enumerate(ladder))
                try:
                    trel = round((datetime.fromisoformat(sec) - t_zero).total_seconds(), 3)
                except (ValueError, TypeError):
                    trel = ""
                w.writerow([sec, trel, ch, *counts, tot,
                            round(counts[3] / tot, 4) if tot else "",
                            round(mbps / tot, 3) if tot else ""])

    dur = None
    if ts_first and ts_last:
        try:
            dur = (datetime.fromisoformat(ts_last) - datetime.fromisoformat(ts_first)).total_seconds()
        except ValueError:
            dur = None

    cfg = unit.config
    census = {
        "unit_id": unit.unit_id, "round": unit.round, "tech": unit.tech,
        "location": unit.location, "distance_m": unit.distance_m,
        "variant": unit.variant, "log": str(log), "log_bytes": log.stat().st_size,
        "config": {"rx_gain": cfg.rx_gain, "tx_gain": cfg.tx_gain,
                   "tdd": cfg.tdd_pattern, "bandwidth_mhz": cfg.bandwidth_mhz,
                   "nof_prbs": cfg.nof_prbs},
        "ts_first": ts_first, "ts_last": ts_last, "duration_s": dur,
        "lines_total": n_lines, "bytes_total": n_bytes,
        "lines_continuation": n_cont, "bytes_continuation": n_cont_bytes,
        "continuation_byte_share": (n_cont_bytes / n_bytes) if n_bytes else None,
        "bytes_per_s": (n_bytes / dur) if dur else None,
        "gb_per_hour": (n_bytes / dur * 3600 / 1e9) if dur else None,
        "metrics_lines": n_metrics,
        "metrics_line_share": (n_metrics / n_lines) if n_lines else None,
        "rsrp_ovl_reports": n_rsrp_ovl,
        "lines_by_layer": dict(census_layer.most_common()),
        "bytes_by_layer": dict(census_layer_bytes.most_common()),
        "lines_by_level": dict(census_level),
        "event_counts": dict(event_counts.most_common()),
        "top_warning_templates": dict(templates.most_common(25)),
    }
    (out / "census.json").write_text(json.dumps(census, indent=2), encoding="utf-8")
    (out / "phy_summary.json").write_text(
        json.dumps({"unit_id": unit.unit_id,
                    **{k: v.summary() for k, v in phy.items() if v.n}},
                   indent=2), encoding="utf-8")
    return census
