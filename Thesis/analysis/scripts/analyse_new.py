"""Join the 2026-08-02 gNB metrics to each iperf3 rep, and compare with the
original 2026-07-25 5G campaign."""
import pandas as pd
import numpy as np

SP = r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad/"
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 70)

reps = pd.read_csv(SP + "new_iperf_reps.csv", parse_dates=["start_utc"])
met = pd.read_csv(SP + "new_metrics.csv", parse_dates=["ts"])

DIST = {"Loc1_2m": 2, "Loc2_5m": 5, "Loc3_10m": 10}
reps["dist"] = reps.location.map(DIST)
met["dist"] = met.location.map(DIST)

# tag each metrics report with the rep whose 20 s window contains it
met["rep_key"] = None
for _, r in reps.iterrows():
    lo = r.start_utc
    hi = lo + pd.Timedelta(seconds=21)
    sel = (met.location == r.location) & (met.ts >= lo) & (met.ts < hi)
    met.loc[sel, "rep_key"] = f"{r.location}|{r.protocol}|{r.direction}|{r.rep}"

tagged = met[met.rep_key.notna()].copy()
parts = tagged.rep_key.str.split("|", expand=True)
tagged[["location", "protocol", "direction", "rep"]] = parts
tagged["dist"] = tagged.location.map(DIST)
# drop the first 5 s of each rep (TCP ramp-up), per the agreed methodology
tagged["sec"] = tagged.groupby("rep_key").cumcount()
steady = tagged[tagged.sec >= 5]

print(f"{len(tagged)} of {len(met)} metrics reports fall inside a rep window "
      f"({len(steady)} after dropping first 5 s)\n")

print("=" * 170)
print("NEW CAMPAIGN (2026-08-02) — application throughput, 3-4 reps per condition")
print("=" * 170)
g = reps.groupby(["dist", "protocol", "direction"]).agg(
    n=("rep", "size"),
    mean_Mbps=("receiver_Mbps", "mean"),
    min_Mbps=("receiver_Mbps", "min"),
    max_Mbps=("receiver_Mbps", "max"),
    sd=("receiver_Mbps", "std"),
    retr=("sender_retr", "mean"),
).round(2)
print(g.to_string())

print()
print("=" * 170)
print("RADIO KPIs inside each rep window (steady state, from [METRICS] Scheduler UE)")
print("=" * 170)
rg = steady.groupby(["dist", "protocol", "direction"]).agg(
    n=("cqi", "size"),
    cqi=("cqi", "mean"),
    dl_mcs=("dl_mcs", "mean"), ul_mcs=("ul_mcs", "mean"),
    dl_err=("dl_error_rate", "mean"), ul_err=("ul_error_rate", "mean"),
    pusch_snr=("pusch_snr_db", "mean"),
    phr=("last_phr", "mean"),
    ovl_pct=("rsrp_ovl", lambda s: 100 * s.mean()),
    ul_prbs=("ul_nof_prbs", "mean"), dl_prbs=("dl_nof_prbs", "mean"),
    bsr_kB=("bsr", lambda s: s.mean() / 1e3),
    ul_grants=("ul_nof_ok", "mean"),
).round(2)
print(rg.to_string())

print()
print("=" * 170)
print("OLD (2026-07-25) vs NEW (2026-08-02) — 5G only, mean Mb/s")
print("=" * 170)
old = pd.read_csv(SP + "active_samples.csv")
old = old[old.tech == "5G"]
old["load"] = np.where(old.direction == "DL", old.dl_brate, old.ul_brate)
o = (old.groupby(["distance_m", "protocol", "direction"])["load"].mean() / 1e6).round(2)
o.index.names = ["dist", "protocol", "direction"]
n = reps.groupby(["dist", "protocol", "direction"])["receiver_Mbps"].mean().round(2)
cmp = pd.DataFrame({"old_2026-07-25": o, "new_2026-08-02": n})
cmp["change"] = (cmp["new_2026-08-02"] / cmp["old_2026-07-25"]).round(2)
print(cmp.to_string())

print()
print("=== Same comparison against the 4G baseline (n=1, unchanged) ===")
old4 = pd.read_csv(SP + "active_samples.csv")
old4 = old4[old4.tech == "4G"]
old4["load"] = np.where(old4.direction == "DL", old4.dl_brate, old4.ul_brate)
b = (old4.groupby(["distance_m", "protocol", "direction"])["load"].mean() / 1e6).round(2)
b.index.names = ["dist", "protocol", "direction"]
cmp2 = pd.DataFrame({"4G_baseline": b, "5G_old": o, "5G_new": n})
cmp2["new_vs_4G"] = (cmp2["5G_new"] / cmp2["4G_baseline"]).round(2)
print(cmp2.to_string())

print()
print("=== Old vs new radio KPIs (5G uplink) ===")
oldm = pd.read_csv(SP + "active_samples.csv")
oldm = oldm[(oldm.tech == "5G")]
oldcmp = oldm.groupby(["distance_m", "direction"]).agg(
    old_ul_mcs=("ul_mcs", "mean"), old_ul_snr=("ul_snr", "mean"),
    old_phr=("ul_phr", "mean")).round(2)
newcmp = steady.groupby(["dist", "direction"]).agg(
    new_ul_mcs=("ul_mcs", "mean"), new_ul_snr=("pusch_snr_db", "mean"),
    new_phr=("last_phr", "mean")).round(2)
oldcmp.index.names = ["dist", "direction"]
print(pd.concat([oldcmp, newcmp], axis=1).to_string())

steady.to_csv(SP + "new_steady_metrics.csv", index=False)
g.to_csv(SP + "new_throughput_summary.csv")
print("\nwrote new_steady_metrics.csv, new_throughput_summary.csv")
