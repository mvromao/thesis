"""Round 1 `trace.log` console metric tables.

Round 1 predates `metrics: enable_log: true`, so its per-second KPIs exist only
as the console table srsRAN prints to stdout. Two consequences the rest of the
pipeline has to respect:

  * **The rows carry no timestamp.** They can be ordered but not aligned to
    wall-clock, so Round 1 rows are sequence-aligned to their test, never
    time-joined. There is exactly one test per Round 1 log, which is what makes
    that acceptable.
  * **4G and 5G print different columns.** 4G reports `pucch` and `phr` but no
    RSRP or timing advance; 5G reports `pusch` SINR, `rsrp` and `ta` but no
    PUCCH SNR. Any 4G-vs-5G comparison is limited to the intersection.

The header block repeats every ~10 rows and is skipped.
"""
from __future__ import annotations

from .units import val

# 5G:  pci rnti | cqi ri mcs brate ok nok (%) dl_bs | pusch rsrp ri mcs brate ok nok (%) bsr ta phr
NR_LEFT = ["pci", "rnti"]
NR_DL = ["dl_cqi", "dl_ri", "dl_mcs", "dl_brate_bps", "dl_ok", "dl_nok",
         "dl_bler", "dl_bs_bytes"]
NR_UL = ["ul_sinr_db", "ul_rsrp_db", "ul_ri", "ul_mcs", "ul_brate_bps", "ul_ok",
         "ul_nok", "ul_bler", "bsr_bytes", "ta_ns", "phr_db"]

# 4G:  rat pci rnti cqi ri mcs brate ok nok (%) | pusch pucch phr mcs brate ok nok (%) bsr
LTE_LEFT = ["rat", "pci", "rnti", "dl_cqi", "dl_ri", "dl_mcs", "dl_brate_bps",
            "dl_ok", "dl_nok", "dl_bler"]
LTE_UL = ["ul_sinr_db", "ul_pucch_db", "phr_db", "ul_mcs", "ul_brate_bps",
          "ul_ok", "ul_nok", "ul_bler", "bsr_bytes"]

_SKIP = ("---", "pci", "rat", "|--")


def _row(names, toks):
    return {n: val(t) for n, t in zip(names, toks)}


def parse(path, tech):
    """Return a list of per-second dicts, in printed order."""
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith(_SKIP) or "|-" in s:
            continue
        if "|" not in s:
            continue
        parts = [p for p in s.split("|")]
        try:
            if tech == "4G":
                if len(parts) != 2:
                    continue
                left, ul = parts[0].split(), parts[1].split()
                if len(left) < len(LTE_LEFT) or len(ul) < len(LTE_UL):
                    continue
                r = _row(LTE_LEFT, left)
                r.update(_row(LTE_UL, ul))
                r["rat"] = left[0]          # 'lte' is not a number
            else:
                if len(parts) != 3:
                    continue
                left, dl, ul = (p.split() for p in parts)
                if len(left) < 2 or len(dl) < len(NR_DL) or len(ul) < len(NR_UL):
                    continue
                r = _row(NR_LEFT, left)
                r.update(_row(NR_DL, dl))
                r.update(_row(NR_UL, ul))
        except (ValueError, IndexError):
            continue
        r["idx"] = len(rows)
        rows.append(r)
    return rows


def active(rows, direction, frac=0.20):
    """Rows where the test was actually carrying traffic.

    The console prints continuously, including the idle stretches before and
    after the iperf3 run; averaging over those understates throughput by more
    than the effect being measured.

    A sample is active when the bit rate *in the direction under test* reaches
    `frac` of that test's own peak. This relative rule is inherited from the
    superseded `scripts/analyse.py` (`df.load_brate >= 0.20 * peak`) and is kept
    deliberately: every Round 1 number already published in FINDINGS.md and
    DATA_INVENTORY.md was computed with it, so changing it would silently move
    the 4G baseline the whole comparison rests on. It is also the better rule --
    an absolute floor cannot serve both a 50 Mb/s downlink and a 0.5 Mb/s
    uplink test.
    """
    key = "dl_brate_bps" if direction == "DL" else "ul_brate_bps"
    vals = [v for r in rows if (v := r.get(key)) is not None]
    if not vals:
        return []
    thr = frac * max(vals)
    return [r for r in rows if (r.get(key) or 0) >= thr]
