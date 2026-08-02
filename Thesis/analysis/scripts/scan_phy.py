"""Per-transmission PHY extraction from the 24 srsRAN stack traces.

Uses a tolerant key=value tokeniser rather than rigid regexes, because srsRAN
adds/removes fields depending on what was multiplexed in the slot (e.g. the
optional `ack=` field when HARQ feedback rides on PUSCH).

Per test it measures:
  * first-transmission uplink BLER (crc=OK/KO on PUSCH)
  * HARQ retransmission share (rv != 0)
  * SINR / SNR distribution measured at the base station
  * PRB occupancy
  * PHY processing time per channel (t=..us) -> real-time headroom of the
    software base station on commodity hardware
"""
import re
import json
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import statistics as st

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

CH = re.compile(r"\b(PUSCH|PDSCH|PUCCH|PDCCH):")
# collapse "[26, 29)" -> "[26-29)" and "(2, 13)" -> "(2-13)" so values are token-safe
SPACED = re.compile(r"([\[(])(\d+),\s*(\d+)([)\]])")
KV = re.compile(r"(\w+)=([^\s,]+)")
RANGE = re.compile(r"^[\[(](\d+)-(\d+)[)\]]$")
NUMTOK = re.compile(r"^(-?\d+\.?\d*)")


def val(s):
    """'11.8dB' -> 11.8 ; '{157}' -> 157 ; '[26-43)' -> width 17 ; 'OK' -> None"""
    s = s.strip("{}")
    m = RANGE.match(s)
    if m:
        return int(m.group(2)) - int(m.group(1))
    m = NUMTOK.match(s)
    return float(m.group(1)) if m else None


def summarise(vals, name, pcts=(1, 5, 25, 50, 75, 95, 99, 99.9)):
    if not vals:
        return {}
    vs = sorted(vals)
    n = len(vs)
    out = {f"{name}_n": n, f"{name}_mean": round(st.fmean(vs), 3),
           f"{name}_min": round(vs[0], 3), f"{name}_max": round(vs[-1], 3)}
    if n > 1:
        out[f"{name}_sd"] = round(st.pstdev(vs), 3)
    for p in pcts:
        out[f"{name}_p{p}".replace(".", "_")] = round(vs[min(n - 1, int(p / 100 * n))], 3)
    return out


def scan(folder: Path):
    tech, loc, protocol, direction = folder.parts[-4:]
    log = next((folder / f for f in ("gnb.log", "enb.log") if (folder / f).exists()), None)
    r = {"tech": tech, "location": loc, "protocol": protocol, "direction": direction}
    if log is None:
        return r

    acc = {c: {"sinr": [], "t": [], "prb": [], "tbs": [], "iter": [],
               "epre": [], "ta": [], "cfo": [], "symb": []}
           for c in ("PUSCH", "PDSCH", "PUCCH", "PDCCH")}
    crc = Counter()
    rv = {"PUSCH": Counter(), "PDSCH": Counter()}
    mod = {"PUSCH": Counter(), "PDSCH": Counter()}
    ack_on_pusch = 0
    n_unmatched_crc = 0

    with open(log, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = CH.search(line)
            if not m:
                if "crc=" in line:
                    n_unmatched_crc += 1
                continue
            ch = m.group(1)
            body = SPACED.sub(r"\1\2-\3\4", line[m.end():])
            kv = dict(KV.findall(body))
            a = acc[ch]

            if ch in ("PUSCH", "PDSCH"):
                if "rv" in kv:
                    rv[ch][kv["rv"].strip("{}")] += 1
                if "mod" in kv:
                    mod[ch][kv["mod"].strip("{}")] += 1
                for src, dst in (("tbs", "tbs"),):
                    if src in kv and (v := val(kv[src])) is not None:
                        a[dst].append(v)
                # PRB width: 5G 'prb=[a-b)', 4G PUSCH 'rb=(a-b)', 4G PDSCH 'nof_prb=N'
                for k in ("prb", "rb", "nof_prb"):
                    if k in kv and (v := val(kv[k])) is not None:
                        a["prb"].append(v)
                        break
                if "symb" in kv and (v := val(kv["symb"])) is not None:
                    a["symb"].append(v)

            if ch == "PUSCH":
                if "crc" in kv:
                    crc[kv["crc"]] += 1
                if "ack" in kv:
                    ack_on_pusch += 1
                for k, dst in (("sinr", "sinr"), ("snr", "sinr"), ("iter", "iter"),
                               ("avg_iter", "iter"), ("epre", "epre"), ("ta", "ta"),
                               ("cfo", "cfo")):
                    if k in kv and (v := val(kv[k])) is not None:
                        a[dst].append(v)
            elif ch == "PUCCH":
                if "sinr" in kv and (v := val(kv["sinr"])) is not None:
                    a["sinr"].append(v)

            if "t" in kv and (v := val(kv["t"])) is not None:
                a["t"].append(v)

    for ch in ("PUSCH", "PDSCH", "PUCCH", "PDCCH"):
        a = acc[ch]
        p = ch.lower()
        r.update(summarise(a["t"], f"{p}_proc_us"))
        if a["sinr"]:
            r.update(summarise(a["sinr"], f"{p}_sinr"))
        if a["prb"]:
            r.update(summarise(a["prb"], f"{p}_prb"))
        if a["iter"]:
            r.update(summarise(a["iter"], f"{p}_ldpc_iter"))
        if a["epre"]:
            r.update(summarise(a["epre"], f"{p}_epre"))
        if a["ta"]:
            r.update(summarise(a["ta"], f"{p}_ta_us"))
        if a["cfo"]:
            r.update(summarise(a["cfo"], f"{p}_cfo_hz"))
        if a["tbs"]:
            r[f"{p}_tbs_total_MB"] = round(sum(a["tbs"]) / 1e6, 3)
            r[f"{p}_tbs_mean_B"] = round(st.fmean(a["tbs"]), 1)
        r[f"n_{p}"] = len(a["t"]) or len(a["tbs"])

    r["crc_ok"], r["crc_ko"] = crc["OK"], crc["KO"]
    tot = crc["OK"] + crc["KO"]
    r["ul_bler_pct"] = round(100 * crc["KO"] / tot, 2) if tot else None
    r["ack_on_pusch"] = ack_on_pusch
    r["unmatched_crc_lines"] = n_unmatched_crc
    for ch in ("PUSCH", "PDSCH"):
        p = ch.lower()
        tt = sum(rv[ch].values())
        r[f"{p}_retx_pct"] = round(100 * sum(v for k, v in rv[ch].items() if k != "0") / tt, 2) if tt else None
        r[f"{p}_rv"] = dict(rv[ch])
        r[f"{p}_mod"] = dict(mod[ch])
    return r


def main():
    folders = sorted(p.parent for p in ROOT.glob("*/*/*/*/trace.log"))
    out = []
    with ProcessPoolExecutor(max_workers=6) as ex:
        for r in ex.map(scan, folders):
            out.append(r)
            print(f"done {r['tech']}/{r['location']}/{r['protocol']}/{r['direction']} "
                  f"pusch={r.get('n_pusch')} pdsch={r.get('n_pdsch')} "
                  f"ulBLER={r.get('ul_bler_pct')}% unmatched={r['unmatched_crc_lines']}",
                  flush=True)
    (OUT / "phy.json").write_text(json.dumps(out, indent=1))
    print("wrote phy.json")


if __name__ == "__main__":
    main()
