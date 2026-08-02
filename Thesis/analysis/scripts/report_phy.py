import json
import pandas as pd

SP = r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad/"
pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 80)

d = pd.DataFrame(json.loads(open(SP + "phy.json").read()))
d["dist"] = d.location.str.extract(r"(\d+)m$").astype(int)
d = d.sort_values(["tech", "dist", "protocol", "direction"]).reset_index(drop=True)
k = ["tech", "dist", "protocol", "direction"]

print("=" * 190)
print("TABLE 5 — Uplink PHY at the base station (first-transmission BLER + HARQ)")
print("=" * 190)
print(d[k + ["n_pusch", "crc_ok", "crc_ko", "ul_bler_pct", "pusch_retx_pct",
             "pusch_sinr_mean", "pusch_sinr_p5", "pusch_sinr_p50", "pusch_sinr_sd",
             "pusch_ldpc_iter_mean", "ack_on_pusch"]].to_string(index=False))

print()
print("=" * 190)
print("TABLE 6 — PHY processing time on the host CPU (microseconds per transmission)")
print("  5G slot budget @30 kHz SCS = 500 us   |   4G subframe budget = 1000 us")
print("=" * 190)
cols = [c for c in ["pusch_proc_us_mean", "pusch_proc_us_p50", "pusch_proc_us_p95",
                    "pusch_proc_us_p99", "pusch_proc_us_p99_9", "pusch_proc_us_max",
                    "pdsch_proc_us_mean", "pdsch_proc_us_p95", "pdsch_proc_us_p99",
                    "pdsch_proc_us_max", "pdcch_proc_us_mean", "pucch_proc_us_mean"]
        if c in d.columns]
print(d[k + cols].to_string(index=False))

print()
print("=== Modulation usage (share of transmissions) ===")
for ch in ("pusch", "pdsch"):
    rows = []
    for _, r in d.iterrows():
        m = r[f"{ch}_mod"] or {}
        tot = sum(m.values()) or 1
        rows.append({**{x: r[x] for x in k},
                     **{kk: round(100 * vv / tot, 1) for kk, vv in sorted(m.items())}})
    print(f"\n-- {ch.upper()} modulation % (4G codes: 2=QPSK 4=16QAM 6=64QAM 8=256QAM) --")
    print(pd.DataFrame(rows).fillna(0).to_string(index=False))

print()
print("=== PRB occupancy (of 50 PRB in 4G / 51 PRB in 5G) ===")
pc = [c for c in ["pusch_prb_mean", "pusch_prb_p95", "pdsch_prb_mean", "pdsch_prb_p95"] if c in d.columns]
print(d[k + pc].to_string(index=False))

print()
print("=== 4G-only radio diagnostics (BladeRF): EPRE, timing advance, carrier freq offset ===")
lte = d[d.tech == "4G"]
lc = [c for c in ["pusch_epre_mean", "pusch_epre_p5", "pusch_ta_us_mean", "pusch_ta_us_max",
                  "pusch_cfo_hz_mean", "pusch_cfo_hz_sd", "pusch_cfo_hz_min", "pusch_cfo_hz_max"]
      if c in d.columns]
print(lte[k + lc].to_string(index=False))

print()
print("=== HARQ redundancy-version distribution (uplink) ===")
rows = []
for _, r in d.iterrows():
    rv = r["pusch_rv"] or {}
    tot = sum(rv.values()) or 1
    rows.append({**{x: r[x] for x in k}, "n": tot,
                 **{f"rv{kk}_%": round(100 * vv / tot, 2) for kk, vv in sorted(rv.items())}})
print(pd.DataFrame(rows).fillna(0).to_string(index=False))

d.to_csv(SP + "phy_summary.csv", index=False)
print("\nwrote phy_summary.csv")
