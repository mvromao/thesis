import pandas as pd
import numpy as np

SP = r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad/"
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 70)

reps = pd.read_csv(SP + "aug03_iperf_reps.csv", parse_dates=["start_utc"])
met = pd.read_csv(SP + "aug03_metrics.csv", parse_dates=["ts"])

# tag metrics rows with the rep whose window contains them (windows overrun 20 s, so use
# each rep's actual duration where known, capped at the next rep's start)
reps = reps.sort_values(["location", "start_utc"]).reset_index(drop=True)
met["rep_key"] = None
for i, r in reps.iterrows():
    dur = r.get("receiver_secs")
    if not np.isfinite(dur) or dur <= 0:
        dur = 45
    lo, hi = r.start_utc, r.start_utc + pd.Timedelta(seconds=float(dur) + 1)
    sel = (met.location == r.location) & (met.ts >= lo) & (met.ts < hi)
    met.loc[sel, "rep_key"] = f"{r.location}|{r.protocol}|{r.direction}|{r.rep}"

tg = met[met.rep_key.notna()].copy()
p = tg.rep_key.str.split("|", expand=True)
tg[["location", "protocol", "direction", "rep"]] = p
tg["sec"] = tg.groupby("rep_key").cumcount()
st = tg[tg.sec >= 5]

print("=" * 175)
print("2026-08-03 @ rx_gain 60 — application throughput (phone-side; UL uses SENDER because")
print("  the results exchange failed on the stalled Loc3 runs and reports receiver = 0)")
print("=" * 175)
reps["thr"] = np.where(reps.direction == "UL",
                       reps.mean_Mbps_5s_on, reps.receiver_Mbps)
g = reps.groupby(["location", "protocol", "direction"]).agg(
    n=("rep", "size"), mean=("thr", "mean"), lo=("thr", "min"), hi=("thr", "max"),
    dur_s=("receiver_secs", "mean")).round(2)
print(g.to_string())

print()
print("=" * 175)
print("RADIO KPIs per location/condition (steady state)")
print("=" * 175)
rg = st.groupby(["location", "protocol", "direction"]).agg(
    n=("cqi", "size"), cqi=("cqi", "mean"),
    dl_mcs=("dl_mcs", "mean"), ul_mcs=("ul_mcs", "mean"),
    dl_err=("dl_error_rate", "mean"), ul_err=("ul_error_rate", "mean"),
    snr=("pusch_snr_db", "mean"), phr=("last_phr", "mean"),
    ul_ok=("ul_nof_ok", "mean"), ul_nok=("ul_nof_nok", "mean"),
    ovl=("rsrp_ovl", "sum")).round(2)
rg["ul_grants"] = (rg.ul_ok + rg.ul_nok).round(0)
print(rg.to_string())

print()
print("=" * 175)
print("*** THE TDD ISOLATION TEST — Loc 3, rx_gain 60, uplink only, only TDD differs ***")
print("=" * 175)
iso = st[(st.location.isin(["Location3", "Location3_TDD"])) &
         (st.direction == "UL") & (st.protocol == "TCP")]
t = iso.groupby("location").agg(
    n=("cqi", "size"), snr=("pusch_snr_db", "mean"), ul_mcs=("ul_mcs", "mean"),
    ul_err=("ul_error_rate", "mean"), phr=("last_phr", "mean"),
    ul_ok=("ul_nof_ok", "mean"), ul_nok=("ul_nof_nok", "mean"),
    bsr_kB=("bsr", lambda s: s.mean() / 1e3)).round(2)
t["grants_total"] = (t.ul_ok + t.ul_nok).round(0)
t.index = ["2 DL : 2 UL  (800 UL slots/s)", "3 DL : 1 UL  (400 UL slots/s)"]
print(t.to_string())
thr = reps[(reps.location.isin(["Location3", "Location3_TDD"])) &
           (reps.direction == "UL") & (reps.protocol == "TCP")]
print()
print("throughput (phone sender, steady state):")
for loc, gg in thr.groupby("location"):
    vals = ", ".join(f"{v:.2f}" for v in gg.mean_Mbps_5s_on)
    print(f"  {loc:16s} {vals}   mean {gg.mean_Mbps_5s_on.mean():.2f} Mb/s   "
          f"test overran to {gg.receiver_secs.mean():.0f} s (asked for 20)")

print()
print("=" * 175)
print("rx_gain 70 (2026-08-02)  vs  rx_gain 60 (2026-08-03) — same TDD 2:2, same placement")
print("=" * 175)
old = pd.read_csv(SP + "new_iperf_reps.csv")
oldmap = {"Loc1_2m": "Location1", "Loc2_5m": "Location2", "Loc3_10m": "Location3"}
old["location"] = old.location.map(oldmap)
old["thr"] = np.where(old.direction == "UL", old.mean_Mbps_5s_on, old.receiver_Mbps)
o = old.groupby(["location", "protocol", "direction"])["thr"].mean().round(2)
n = reps[reps.location != "Location3_TDD"].groupby(
    ["location", "protocol", "direction"])["thr"].mean().round(2)
c = pd.DataFrame({"rx_gain_70": o, "rx_gain_60": n})
c["change"] = (c.rx_gain_60 / c.rx_gain_70).round(2)
print(c.to_string())

print()
print("=== radio: rx_gain 70 vs 60, uplink tests ===")
oldm = pd.read_csv(SP + "new_steady_metrics.csv")
oldm["location"] = oldm.location.map(oldmap)
a = oldm[oldm.direction == "UL"].groupby("location").agg(
    snr70=("pusch_snr_db", "mean"), mcs70=("ul_mcs", "mean"),
    bler70=("ul_error_rate", "mean"), phr70=("last_phr", "mean"),
    ovl70=("rsrp_ovl", lambda s: 100 * s.mean())).round(2)
b = st[(st.direction == "UL") & (st.location != "Location3_TDD")].groupby("location").agg(
    snr60=("pusch_snr_db", "mean"), mcs60=("ul_mcs", "mean"),
    bler60=("ul_error_rate", "mean"), phr60=("last_phr", "mean"),
    ovl60=("rsrp_ovl", lambda s: 100 * s.mean())).round(2)
print(pd.concat([a, b], axis=1).to_string())

st.to_csv(SP + "aug03_steady_metrics.csv", index=False)
reps.to_csv(SP + "aug03_reps_with_thr.csv", index=False)
print("\nwrote aug03_steady_metrics.csv")
