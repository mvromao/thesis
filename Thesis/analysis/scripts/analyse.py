"""Summarise the 24 srsRAN traces into thesis-ready KPI tables."""
import pandas as pd
import numpy as np

pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 60)

SP = r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad/"
df = pd.read_csv(SP + "trace_tidy.csv")

# srsRAN 4G reports 99.9 on pucch/rsrp as a "no measurement" sentinel
df.loc[df.ul_pucch_snr == 99.9, "ul_pucch_snr"] = np.nan

# Direction under test -> the bearer that carries the iperf3 payload
df["load_brate"] = np.where(df.direction == "DL", df.dl_brate, df.ul_brate)
df["load_bler"] = np.where(df.direction == "DL", df.dl_bler, df.ul_bler)
df["load_mcs"] = np.where(df.direction == "DL", df.dl_mcs, df.ul_mcs)

# "Active" = samples carrying real traffic. Threshold at 20% of that test's peak,
# which cleanly separates the iperf transfer from attach/idle keep-alive samples.
peak = df.groupby(["tech", "distance_m", "protocol", "direction"])["load_brate"].transform("max")
df["active"] = df.load_brate >= 0.20 * peak
act = df[df.active].copy()

KEY = ["tech", "distance_m", "protocol", "direction"]


def q(s, p):
    return s.quantile(p)


summary = act.groupby(KEY).agg(
    n_active=("load_brate", "size"),
    mean_Mbps=("load_brate", lambda s: s.mean() / 1e6),
    p50_Mbps=("load_brate", lambda s: s.median() / 1e6),
    p05_Mbps=("load_brate", lambda s: q(s, 0.05) / 1e6),
    peak_Mbps=("load_brate", lambda s: s.max() / 1e6),
    cov=("load_brate", lambda s: s.std() / s.mean()),
    mean_bler=("load_bler", "mean"),
    max_bler=("load_bler", "max"),
    mean_mcs=("load_mcs", "mean"),
    dl_cqi=("dl_cqi", "mean"),
    ul_snr=("ul_snr", "mean"),
    ul_rsrp=("ul_rsrp", "mean"),
    ul_phr=("ul_phr", "mean"),
    ta_ns=("ul_ta", lambda s: s.mean() * 1e9 if s.notna().any() else np.nan),
).round(2)

print("=" * 150)
print("TABLE 1 — Steady-state KPIs per test (active samples only)")
print("=" * 150)
print(summary.to_string())

print()
print("=" * 150)
print("TABLE 2 — 5G vs 4G throughput gain (mean Mb/s over active window)")
print("=" * 150)
piv = act.groupby(KEY)["load_brate"].mean().unstack("tech") / 1e6
piv["gain_5G_over_4G"] = (piv["5G"] / piv["4G"]).round(2)
print(piv.round(2).to_string())

print()
print("=== Aggregate by tech/direction ===")
agg = act.groupby(["tech", "direction"]).agg(
    mean_Mbps=("load_brate", lambda s: s.mean() / 1e6),
    mean_bler=("load_bler", "mean"),
    mean_mcs=("load_mcs", "mean"),
).round(2)
print(agg.to_string())

print()
print("=== DL/UL asymmetry ratio (mean DL Mb/s / mean UL Mb/s) ===")
a = act.groupby(["tech", "distance_m", "protocol", "direction"])["load_brate"].mean().unstack("direction") / 1e6
a["DL_UL_ratio"] = (a["DL"] / a["UL"]).round(1)
print(a.round(2).to_string())

print()
print("=== TCP vs UDP (same tech/dist/dir) ===")
t = act.groupby(["tech", "distance_m", "direction", "protocol"])["load_brate"].mean().unstack("protocol") / 1e6
t["UDP_over_TCP"] = (t["UDP"] / t["TCP"]).round(2)
print(t.round(2).to_string())

print()
print("=== Radio conditions vs distance (all active samples) ===")
rc = act.groupby(["tech", "distance_m"]).agg(
    dl_cqi=("dl_cqi", "mean"),
    ul_snr=("ul_snr", "mean"),
    ul_rsrp=("ul_rsrp", "mean"),
    ul_phr=("ul_phr", "mean"),
    dl_mcs=("dl_mcs", "mean"),
    ul_mcs=("ul_mcs", "mean"),
    dl_bler=("dl_bler", "mean"),
    ul_bler=("ul_bler", "mean"),
    ta_ns=("ul_ta", "mean"),
).round(2)
print(rc.to_string())

print()
print("=== UL buffer status report (BSR) — backlog indicator, UL tests only ===")
ul = act[act.direction == "UL"]
print(ul.groupby(["tech", "distance_m", "protocol"]).agg(
    mean_bsr_kB=("ul_bsr", lambda s: s.mean() / 1e3),
    max_bsr_kB=("ul_bsr", lambda s: s.max() / 1e3),
    mean_ul_mcs=("ul_mcs", "mean"),
    mean_ul_Mbps=("ul_brate", lambda s: s.mean() / 1e6),
).round(2).to_string())

act.to_csv(SP + "active_samples.csv", index=False)
summary.to_csv(SP + "summary_kpis.csv")
print("\nwrote active_samples.csv, summary_kpis.csv")
