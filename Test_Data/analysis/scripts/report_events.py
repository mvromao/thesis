"""Turn events.json into thesis-ready tables."""
import json
import pandas as pd
from collections import Counter

SP = r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad/"
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_colwidth", 130)

data = json.loads(open(SP + "events.json").read())
rows = []
for d in data:
    ev, lv, ly = d["events"], d["levels"], d["layers"]
    crc_ok, crc_ko = ev.get("crc_ok", 0), ev.get("crc_ko", 0)
    rows.append({
        "tech": d["tech"], "dist": int(d["location"].split("_")[-1].rstrip("m")),
        "proto": d["protocol"], "dir": d["direction"],
        "lines_M": round(d["lines"] / 1e6, 2),
        "hex_pct": round(100 * d["hex_lines"] / max(d["lines"], 1), 1),
        "info": lv.get("I", 0), "warn": lv.get("W", 0), "err": lv.get("E", 0),
        "dbg": lv.get("D", 0),
        "phy_late": ev.get("phy_rt_failure", 0),
        "fapi_late": ev.get("fapi_late", 0),
        "mod_busy": ev.get("modulator_busy", 0),
        "rf_ovf": ev.get("rf_overflow", 0),
        "rf_udf": ev.get("rf_underflow", 0),
        "rlf": ev.get("rlf", 0),
        "sched_errind": ev.get("sched_err_ind", 0),
        "harq_max": ev.get("harq_maxretx", 0),
        "prach": ev.get("rach", 0),
        "reest": ev.get("reest", 0),
        "crc_ok": crc_ok, "crc_ko": crc_ko,
        "crc_ko_pct": round(100 * crc_ko / max(crc_ok + crc_ko, 1), 2) if (crc_ok + crc_ko) else None,
    })

df = pd.DataFrame(rows).sort_values(["tech", "dist", "proto", "dir"]).reset_index(drop=True)

print("=" * 200)
print("TABLE 3 — Log volume and stack anomalies per test")
print("=" * 200)
print(df.to_string(index=False))

print()
print("=== Totals by technology ===")
num = df.select_dtypes("number").columns.drop(["dist", "crc_ko_pct", "hex_pct"])
print(df.groupby("tech")[list(num)].sum().to_string())

print()
print("=== Real-time / SDR health per tech (sum) ===")
print(df.groupby("tech")[["phy_late", "fapi_late", "mod_busy", "rf_ovf", "rf_udf",
                          "sched_errind", "rlf"]].sum().to_string())

print()
print("=== PHY late events vs distance (5G only) ===")
print(df[df.tech == "5G"].groupby(["dist", "dir"])[["phy_late", "fapi_late", "mod_busy"]].sum().to_string())

print()
print("=" * 200)
print("TABLE 4 — Distinct WARNING/ERROR message templates (all 24 logs, numbers -> #)")
print("=" * 200)
tmpl = Counter()
tmpl_by_tech = {"4G": Counter(), "5G": Counter()}
for d in data:
    for k, v in d["templates"].items():
        tmpl[k] += v
        tmpl_by_tech[d["tech"]][k] += v
t = pd.DataFrame([{"count": v, "4G": tmpl_by_tech["4G"][k], "5G": tmpl_by_tech["5G"][k],
                   "template": k} for k, v in tmpl.most_common(40)])
print(t.to_string(index=False))

print()
print("=== Per-layer log line share (%) by tech ===")
lay = {}
for d in data:
    lay.setdefault(d["tech"], Counter()).update(d["layers"])
ldf = pd.DataFrame(lay).fillna(0)
ldf = (100 * ldf / ldf.sum()).round(2).sort_values("5G", ascending=False)
print(ldf.head(18).to_string())

df.to_csv(SP + "event_summary.csv", index=False)
print("\nwrote event_summary.csv")
