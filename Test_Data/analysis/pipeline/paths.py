"""The run registry: the single place that knows where data lives and what it is.

Every earlier script hardcoded its own root and its own folder-name assumptions.
This module replaces all of them. It resolves paths *and* reads each campaign's
radio configuration out of the log's own `[CONFIG ]` dump, so provenance comes
from the data rather than from folder names.

Two units of analysis, deliberately distinct:

  LogUnit  one stack log to stream once (31 total).  In Round 1 a log covers a
           single test; in Rounds 2-3 a single log covers a whole location
           session of ~12 iperf3 repetitions.
  Rep      one iperf3 measurement (102 total).  This is what the results tables
           are keyed on.

Naming traps encoded here so nobody has to remember them:

  * Location B is 6 m.  Folder names say `Loc2_5m` / `Location2` and the
    analysis CSVs say "5 m" -- that was a nominal figure used before the room
    was surveyed with a tape measure.  See `5 - Implementation.tex`, note on
    location B.  `distance_m` is the true value; `legacy_label` keeps the old
    one so old and new outputs can be joined.
  * Round 1 5G logs contain no `[METRICS ]` lines at all; per-second metrics for
    that round exist only in the untimestamped `trace.log` console table.
  * `1 - 28-Jul/**/enb_metrics.csv` is a stub containing only `#eof`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# thesis/Test_Data/analysis/pipeline/paths.py -> thesis/Test_Data
TEST_DATA = Path(__file__).resolve().parents[2]
TESTING_DATA = TEST_DATA / "testing_data"
ANALYSIS = TEST_DATA / "analysis"

EXTRACTED = ANALYSIS / "extracted"
DATA_V2 = ANALYSIS / "data_v2"
DATA_BASELINE = ANALYSIS / "data"          # the pre-rebuild CSVs, kept for regression

ROUND_DIR = {
    1: TESTING_DATA / "1 - 28-Jul",
    2: TESTING_DATA / "2 - 02-Aug",
    3: TESTING_DATA / "3 - 03-Aug",
}
CAMPAIGN = {1: "2026-07-25/28", 2: "2026-08-02", 3: "2026-08-03"}

PINGS = TESTING_DATA / "pings"
CORE_LOGS = TESTING_DATA / "logs"

# folder token -> (location letter, true distance in metres)
LOCATIONS = {
    "Loc_1_2m": ("A", 2), "Loc1_2m": ("A", 2), "Location1": ("A", 2),
    "Loc_2_5m": ("B", 6), "Loc2_5m": ("B", 6), "Location2": ("B", 6),
    "Loc_3_10m": ("C", 10), "Loc3_10m": ("C", 10), "Location3": ("C", 10),
    "Location3_TDD": ("C", 10),
}


@dataclass(frozen=True)
class RadioConfig:
    """Read from the log's own startup dump, never assumed."""
    tx_gain: float | None = None
    rx_gain: float | None = None
    nof_dl_slots: int | None = None
    nof_ul_slots: int | None = None
    nof_dl_symbols: int | None = None
    nof_ul_symbols: int | None = None
    dl_arfcn: int | None = None
    bandwidth_mhz: float | None = None
    band: int | None = None
    nof_prbs: int | None = None

    @property
    def tdd_pattern(self) -> str:
        if self.nof_dl_slots is None:
            return "n/a"
        return f"{self.nof_dl_slots}DL:{self.nof_ul_slots}UL"

    @property
    def ul_slot_fraction(self) -> float | None:
        """Share of slots carrying uplink -- the structural airtime ceiling."""
        if self.nof_dl_slots is None or self.nof_ul_slots is None:
            return None
        total = self.nof_dl_slots + self.nof_ul_slots
        return self.nof_ul_slots / total if total else None


@dataclass(frozen=True)
class LogUnit:
    """One stack log = one streaming pass in stage 1."""
    unit_id: str
    round: int
    tech: str
    location: str
    distance_m: int
    variant: str                 # "" or "TDD31" for the Round 3 isolation run
    stack_log: Path
    console_log: Path | None = None
    mac_pcap: Path | None = None
    ngap_pcap: Path | None = None
    server_json: Path | None = None
    legacy_label: str = ""

    @property
    def out_dir(self) -> Path:
        return EXTRACTED / self.unit_id

    @property
    def config(self) -> RadioConfig:
        return read_config(self.stack_log)


@dataclass(frozen=True)
class Rep:
    """One iperf3 measurement -- the key for every results table."""
    rep_id: str
    unit_id: str
    round: int
    tech: str
    location: str
    distance_m: int
    protocol: str                # TCP | UDP
    direction: str               # DL | UL
    rep: int
    variant: str = ""
    client_export: Path | None = None
    iteration: int = 1           # position within a multi-iteration export file
    console_log: Path | None = None


# --------------------------------------------------------------------------
# radio configuration, read from the log header
# --------------------------------------------------------------------------

_CFG_KEYS = {
    "tx_gain": ("tx_gain", float), "rx_gain": ("rx_gain", float),
    "nof_dl_slots": ("nof_dl_slots", int), "nof_ul_slots": ("nof_ul_slots", int),
    "nof_dl_symbols": ("nof_dl_symbols", int), "nof_ul_symbols": ("nof_ul_symbols", int),
    "dl_arfcn": ("dl_arfcn", int), "channel_bandwidth_MHz": ("bandwidth_mhz", int),
    "band": ("band", int),
}


# srsenb never dumps its configuration; the only figure it states is the cell
# width, as a PRB count. LTE PRB count -> nominal channel bandwidth.
_PRB_TO_MHZ = {6: 1.4, 15: 3, 25: 5, 50: 10, 75: 15, 100: 20}
_ENB_PRB = re.compile(r"Starting RX/TX thread nof_prb=(\d+)")


@lru_cache(maxsize=64)
def read_config(log: Path) -> RadioConfig:
    """Read the radio configuration out of the log's own startup output.

    5G (`gnb.log`) prints a YAML dump of *only non-default values*, so a missing
    key means "left at default" -- which is exactly how the `pcg_p_nr_fr1`
    power-cap claim was disproven: absence from this dump is evidence.

    4G (`enb.log`) prints no configuration at all, only `nof_prb`. Gains, band
    and duplexing for the 4G runs are therefore *not* recoverable from the data
    and must be cited from `files/enb.conf`; the fields stay None here rather
    than being filled in from folder names or memory.

    Only the header is scanned, never the whole file.
    """
    if log is None or not log.exists():
        return RadioConfig()
    found: dict[str, object] = {}
    with open(log, encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if i > 3000:
                break
            m = _ENB_PRB.search(line)
            if m:
                prb = int(m.group(1))
                found.setdefault("bandwidth_mhz", _PRB_TO_MHZ.get(prb))
                found.setdefault("nof_prbs", prb)
                break
            m = re.match(r"\s*([A-Za-z_]+):\s*(-?[\d.]+)\s*$", line)
            if not m:
                continue
            key, raw = m.groups()
            if key in _CFG_KEYS:
                name, cast = _CFG_KEYS[key]
                if name not in found:
                    found[name] = cast(float(raw))
    return RadioConfig(**found)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------

_R2_EXPORT = re.compile(r"^(TCP|UDP)_(DL|UL)(\d+)\.txt$", re.I)
_IPERF_CMD = re.compile(r"^iperf3 -c .*$", re.M)


def _cond_from_cmd(cmd: str) -> tuple[str, str]:
    """`-R` means reverse mode: the server sends, so the UE is downloading."""
    return ("UDP" if " -u" in cmd else "TCP", "DL" if " -R" in cmd else "UL")


def _round1_units() -> list[LogUnit]:
    units = []
    root = ROUND_DIR[1]
    for tech_dir in sorted(root.glob("[45]G")):
        tech = tech_dir.name
        for loc_dir in sorted(tech_dir.iterdir()):
            if not loc_dir.is_dir() or loc_dir.name not in LOCATIONS:
                continue
            loc, dist = LOCATIONS[loc_dir.name]
            for proto in ("TCP", "UDP"):
                for direction in ("DL", "UL"):
                    d = loc_dir / proto / direction
                    log = next((d / n for n in ("gnb.log", "enb.log") if (d / n).exists()), None)
                    if log is None:
                        continue
                    units.append(LogUnit(
                        unit_id=f"R1_{tech}_{loc}_{proto}_{direction}",
                        round=1, tech=tech, location=loc, distance_m=dist, variant="",
                        stack_log=log,
                        console_log=(d / "trace.log") if (d / "trace.log").exists() else None,
                        mac_pcap=next(iter(d.glob("*_mac.pcap")), None),
                        ngap_pcap=next(iter(d.glob("*_ngap.pcap")), None),
                        legacy_label=loc_dir.name,
                    ))
    return units


def _session_units(rnd: int) -> list[LogUnit]:
    units = []
    for sess in sorted(ROUND_DIR[rnd].iterdir()):
        if not sess.is_dir() or sess.name not in LOCATIONS:
            continue
        loc, dist = LOCATIONS[sess.name]
        log = next(iter(sorted(sess.glob("gnb*.log"))), None)
        if log is None:
            continue
        variant = "TDD31" if sess.name.endswith("_TDD") else ""
        uid = f"R{rnd}_5G_{loc}" + (f"_{variant}" if variant else "")
        units.append(LogUnit(
            unit_id=uid, round=rnd, tech="5G", location=loc, distance_m=dist,
            variant=variant, stack_log=log,
            mac_pcap=next(iter(sess.glob("*_mac.pcap")), None),
            ngap_pcap=next(iter(sess.glob("*_ngap.pcap")), None),
            server_json=next(iter(sorted(sess.glob("test*.json"))), None),
            legacy_label=sess.name,
        ))
    return units


def log_units(rounds=(1, 2, 3)) -> list[LogUnit]:
    """Every stack log to be streamed in stage 1."""
    out: list[LogUnit] = []
    for r in rounds:
        out += _round1_units() if r == 1 else _session_units(r)
    return out


def reps(rounds=(1, 2, 3)) -> list[Rep]:
    """Every iperf3 measurement, resolved to its export file and stack log."""
    out: list[Rep] = []
    by_id = {u.unit_id: u for u in log_units(rounds)}

    for u in by_id.values():
        if u.round == 1:
            # unit_id is R1_<tech>_<loc>_<proto>_<dir>; one test, one repetition
            _, tech, loc, proto, direction = u.unit_id.split("_")
            out.append(Rep(
                rep_id=f"{u.unit_id}_r1", unit_id=u.unit_id, round=1, tech=tech,
                location=loc, distance_m=u.distance_m, protocol=proto,
                direction=direction, rep=1, console_log=u.console_log))
            continue

        sess = u.stack_log.parent
        if u.round == 2:
            for f in sorted(sess.glob("*.txt")):
                m = _R2_EXPORT.match(f.name)
                if not m:
                    continue
                proto, direction, n = m.group(1).upper(), m.group(2).upper(), int(m.group(3))
                out.append(Rep(
                    rep_id=f"{u.unit_id}_{proto}_{direction}_r{n}", unit_id=u.unit_id,
                    round=2, tech="5G", location=u.location, distance_m=u.distance_m,
                    protocol=proto, direction=direction, rep=n, client_export=f))
        else:
            # Round 3 filenames are timestamps; the condition is in the command
            # line inside, and one file may hold several iterations.
            seen: dict[tuple[str, str], int] = {}
            for f in sorted(sess.glob("iPerf3_*.txt")):
                text = f.read_text(encoding="utf-8", errors="ignore")
                cmds = _IPERF_CMD.findall(text)
                for it, cmd in enumerate(cmds, start=1):
                    proto, direction = _cond_from_cmd(cmd)
                    n = seen.get((proto, direction), 0) + 1
                    seen[(proto, direction)] = n
                    suffix = f"_{u.variant}" if u.variant else ""
                    out.append(Rep(
                        rep_id=f"R3_5G_{u.location}{suffix}_{proto}_{direction}_r{n}",
                        unit_id=u.unit_id, round=3, tech="5G", location=u.location,
                        distance_m=u.distance_m, protocol=proto, direction=direction,
                        rep=n, variant=u.variant, client_export=f, iteration=it))
    return out


def ping_captures() -> dict[str, Path]:
    """location letter -> raw ping capture."""
    out = {}
    for p in sorted(PINGS.glob("ping_Loc*")):
        idx = p.name.replace("ping_Loc", "")
        out[{"1": "A", "2": "B", "3": "C"}.get(idx, idx)] = p
    return out
