"""Parse the 24 srsRAN console-metric traces into one tidy CSV.

4G (srsRAN 4G enb) row layout:
  rat pci rnti | cqi ri mcs brate ok nok (%) | pusch pucch phr mcs brate ok nok (%) bsr
5G (srsRAN Project gnb) row layout:
  pci rnti | cqi ri mcs brate ok nok (%) dl_bs | pusch rsrp ri mcs brate ok nok (%) bsr ta phr
"""
import re
import csv
from pathlib import Path

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

SUFFIX = {"k": 1e3, "M": 1e6, "G": 1e9, "n": 1e-9, "u": 1e-6, "m": 1e-3}


def num(tok):
    """srsRAN metric token -> float (None if n/a)."""
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


# a data row must start (after junk) with digits or 'lte'/'nr'
ROW_START = re.compile(r"^[^\dln]*((?:lte|nr)?\s*\d.*)$")


def parse_row(line, tech):
    """Return dict of metrics, or None if the line is not a data row."""
    if "---" in line or "cqi" in line or "connected" in line.lower():
        return None
    m = ROW_START.match(line.rstrip("\n"))
    if not m:
        return None
    body = m.group(1)

    if tech == "4G":
        # 'lte' prefix, single '|' separator
        body = re.sub(r"^(lte|nr)\s+", "", body)
        if "|" not in body:
            return None
        dl_part, ul_part = body.split("|", 1)
        dl = dl_part.split()
        ul = ul_part.split()
        # dl: pci rnti cqi ri mcs brate ok nok (%)
        # ul: pusch pucch phr mcs brate ok nok (%) bsr
        if len(dl) < 9 or len(ul) < 9:
            return None
        return {
            "pci": num(dl[0]), "rnti": dl[1],
            "dl_cqi": num(dl[2]), "dl_ri": num(dl[3]), "dl_mcs": num(dl[4]),
            "dl_brate": num(dl[5]), "dl_ok": num(dl[6]), "dl_nok": num(dl[7]),
            "dl_bler": num(dl[8]), "dl_bs": None,
            "ul_snr": num(ul[0]), "ul_pucch_snr": num(ul[1]), "ul_rsrp": None,
            "ul_phr": num(ul[2]), "ul_ri": None, "ul_mcs": num(ul[3]),
            "ul_brate": num(ul[4]), "ul_ok": num(ul[5]), "ul_nok": num(ul[6]),
            "ul_bler": num(ul[7]), "ul_bsr": num(ul[8]), "ul_ta": None,
        }
    else:
        # 5G: two '|' separators
        parts = body.split("|")
        if len(parts) < 3:
            return None
        head, dl_part, ul_part = parts[0], parts[1], parts[2]
        h, dl, ul = head.split(), dl_part.split(), ul_part.split()
        # head: pci rnti ; dl: cqi ri mcs brate ok nok (%) dl_bs
        # ul: pusch rsrp ri mcs brate ok nok (%) bsr ta phr
        if len(h) < 2 or len(dl) < 8 or len(ul) < 11:
            return None
        return {
            "pci": num(h[0]), "rnti": h[1],
            "dl_cqi": num(dl[0]), "dl_ri": num(dl[1]), "dl_mcs": num(dl[2]),
            "dl_brate": num(dl[3]), "dl_ok": num(dl[4]), "dl_nok": num(dl[5]),
            "dl_bler": num(dl[6]), "dl_bs": num(dl[7]),
            "ul_snr": num(ul[0]), "ul_pucch_snr": None, "ul_rsrp": num(ul[1]),
            "ul_phr": num(ul[10]), "ul_ri": num(ul[2]), "ul_mcs": num(ul[3]),
            "ul_brate": num(ul[4]), "ul_ok": num(ul[5]), "ul_nok": num(ul[6]),
            "ul_bler": num(ul[7]), "ul_bsr": num(ul[8]), "ul_ta": num(ul[9]),
        }


FIELDS = ["tech", "distance_m", "location", "protocol", "direction", "sample",
          "pci", "rnti", "dl_cqi", "dl_ri", "dl_mcs", "dl_brate", "dl_ok",
          "dl_nok", "dl_bler", "dl_bs", "ul_snr", "ul_pucch_snr", "ul_rsrp",
          "ul_phr", "ul_ri", "ul_mcs", "ul_brate", "ul_ok", "ul_nok",
          "ul_bler", "ul_bsr", "ul_ta"]

rows = []
skipped = {}
for trace in sorted(ROOT.glob("*/*/*/*/trace.log")):
    tech, loc, protocol, direction = trace.parts[-5:-1]
    dist = int(re.search(r"(\d+)m$", loc).group(1))
    n_bad = 0
    with open(trace, encoding="utf-8", errors="ignore") as f:
        idx = 0
        for line in f:
            if not line.strip():
                continue
            r = parse_row(line, tech)
            if r is None:
                if not any(t in line for t in ("---", "cqi", "connected")) and line.strip() not in ("q", "~"):
                    n_bad += 1
                continue
            r.update(tech=tech, distance_m=dist, location=loc,
                     protocol=protocol, direction=direction, sample=idx)
            idx += 1
            rows.append(r)
    skipped[f"{tech}/{loc}/{protocol}/{direction}"] = (idx, n_bad)

with open(OUT / "trace_tidy.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)

print(f"parsed {len(rows)} metric rows from {len(skipped)} tests -> trace_tidy.csv")
for k, (n, bad) in sorted(skipped.items()):
    flag = f"  !! {bad} unparsed" if bad else ""
    print(f"  {k:34s} {n:5d} rows{flag}")
