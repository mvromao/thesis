"""Reproduce the Round 1 uplink grants/s + bits-per-grant decomposition (Results Section
"TDD rebalance effects on uplink airtime and throughput") directly from the raw
srsRAN/srsenb console-metric trace.log files.

Saturation rule (must be stated, since it changes the averages): a 1-second reporting row
is "saturated" if its successful+failed uplink grant count is at least 90% of the
technology's structural ceiling (1000/s for 4G FDD, 400/s for the 5G 3:1 TDD pattern used
in Round 1). This drops call-setup/teardown rows and rows still in TCP slow start without
hand-picking any individual second.

bits_per_grant is Sum(ul_brate)/Sum(ul_ok) over the kept rows (bits actually delivered
divided by grants that actually succeeded), not an average of per-row ratios -- the two
differ because seconds carry unequal traffic.
"""
import re
from pathlib import Path

ROOT = Path("/home/mvromao/thesis/Test_Data/testing_data/28-Jul")

SUFFIX = {"k": 1e3, "M": 1e6, "G": 1e9, "n": 1e-9, "u": 1e-6, "m": 1e-3}


def num(tok):
    tok = tok.strip()
    if not tok or tok in ("n/a", "-", ""):
        return None
    tok = tok.rstrip("%")
    if tok and tok[-1] in SUFFIX:
        try:
            return float(tok[:-1]) * SUFFIX[tok[-1]]
        except ValueError:
            return None
    try:
        return float(tok)
    except ValueError:
        return None


ROW_START = re.compile(r"^[^\dln]*((?:lte|nr)?\s*\d.*)$")


def parse_row(line, tech):
    if "---" in line or "cqi" in line or "connected" in line.lower():
        return None
    m = ROW_START.match(line.rstrip("\n"))
    if not m:
        return None
    body = m.group(1)
    if tech == "4G":
        body = re.sub(r"^(lte|nr)\s+", "", body)
        if "|" not in body:
            return None
        ul = body.split("|", 1)[1].split()
        if len(ul) < 9:
            return None
        return {"ul_brate": num(ul[4]), "ul_ok": num(ul[5]), "ul_nok": num(ul[6])}
    else:
        parts = body.split("|")
        if len(parts) < 3:
            return None
        ul = parts[2].split()
        if len(ul) < 11:
            return None
        return {"ul_brate": num(ul[4]), "ul_ok": num(ul[5]), "ul_nok": num(ul[6])}


CEILING = {"4G": 1000, "5G": 400}
RUNS = {
    "4G @ 2 m":  ("4G", ROOT / "4G/Loc_1_2m/TCP/UL/trace.log"),
    "5G @ 2 m":  ("5G", ROOT / "5G/Loc_1_2m/TCP/UL/trace.log"),
    "4G @ 10 m": ("4G", ROOT / "4G/Loc_3_10m/TCP/UL/trace.log"),
    "5G @ 10 m": ("5G", ROOT / "5G/Loc_3_10m/TCP/UL/trace.log"),
}

print(f"{'run':<11} {'n_rows':>7} {'kept':>6} {'grants/s':>9} {'bits/grant':>11} {'Mb/s':>7}")
results = {}
for label, (tech, path) in RUNS.items():
    rows = []
    with open(path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            r = parse_row(line, tech)
            if r and r["ul_brate"] is not None and r["ul_ok"] is not None and r["ul_nok"] is not None:
                rows.append(r)
    thresh = 0.9 * CEILING[tech]
    kept = [r for r in rows if (r["ul_ok"] + r["ul_nok"]) >= thresh]
    total_bits = sum(r["ul_brate"] for r in kept)
    total_ok = sum(r["ul_ok"] for r in kept)
    total_grants = sum(r["ul_ok"] + r["ul_nok"] for r in kept)
    grants_per_s = total_grants / len(kept)
    bits_per_grant = total_bits / total_ok
    mbps = total_bits / len(kept) / 1e6
    results[label] = (grants_per_s, bits_per_grant, mbps)
    print(f"{label:<11} {len(rows):>7} {len(kept):>6} {grants_per_s:>9.1f} {bits_per_grant:>11.0f} {mbps:>7.2f}")

print()
g5, b5_2, _ = results["5G @ 2 m"]
g4, b4_2, _ = results["4G @ 2 m"]
_, b5_10, _ = results["5G @ 10 m"]
_, b4_10, _ = results["4G @ 10 m"]
factorA = g4 / g5
factorB_2 = b4_2 / b5_2
factorB_10 = b4_10 / b5_10
print(f"Factor A (airtime, 4G/5G grants-per-s):        {factorA:.2f}x")
print(f"Factor B @ 2 m  (4G/5G bits-per-grant):         {factorB_2:.2f}x")
print(f"Factor B @ 10 m (4G/5G bits-per-grant):         {factorB_10:.2f}x")
print(f"Predicted deficit @ 2 m  (A x B):  {factorA*factorB_2:.2f}x")
print(f"Predicted deficit @ 10 m (A x B):  {factorA*factorB_10:.2f}x")
