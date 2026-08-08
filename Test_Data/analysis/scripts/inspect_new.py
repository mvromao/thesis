import pandas as pd
import numpy as np

SP = r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad/"
pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 70)
pd.set_option("display.max_rows", 200)

reps = pd.read_csv(SP + "new_iperf_reps.csv", parse_dates=["start_utc"])
st = pd.read_csv(SP + "new_steady_metrics.csv", parse_dates=["ts"])
met = pd.read_csv(SP + "new_metrics.csv", parse_dates=["ts"])

print("=" * 190)
print("PER-REP detail — throughput and radio together")
print("=" * 190)
per = st.groupby(["location", "protocol", "direction", "rep"]).agg(
    n=("cqi", "size"), cqi=("cqi", "mean"), dl_mcs=("dl_mcs", "mean"),
    ul_mcs=("ul_mcs", "mean"), dl_err=("dl_error_rate", "mean"),
    ul_err=("ul_error_rate", "mean"), snr=("pusch_snr_db", "mean"),
    phr=("last_phr", "mean"), ovl=("rsrp_ovl", "sum"),
    ul_ok=("ul_nof_ok", "mean"), ul_nok=("ul_nof_nok", "mean"),
    dl_ok=("dl_nof_ok", "mean"), dl_nok=("dl_nof_nok", "mean"),
).round(2).reset_index()
per["rep"] = per["rep"].astype(int)
r2 = reps[["location", "protocol", "direction", "rep", "receiver_Mbps", "sender_retr"]]
m = per.merge(r2, on=["location", "protocol", "direction", "rep"], how="left")
print(m.sort_values(["location", "protocol", "direction", "rep"]).to_string(index=False))

print()
print("=" * 190)
print("WHOLE-SESSION time series per location (all metrics reports, 1/s) — did conditions drift?")
print("=" * 190)
for loc in ["Loc1_2m", "Loc2_5m", "Loc3_10m"]:
    s = met[met.location == loc].sort_values("ts")
    s = s[s.pusch_snr_db.notna()]
    if s.empty:
        continue
    print(f"\n--- {loc}: {s.ts.min()} .. {s.ts.max()}  ({len(s)} reports) ---")
    # 30-second buckets
    s = s.set_index("ts")
    b = s.resample("30s").agg(
        snr=("pusch_snr_db", "mean"), phr=("last_phr", "mean"),
        ul_mcs=("ul_mcs", "mean"), ul_err=("ul_error_rate", "mean"),
        dl_mcs=("dl_mcs", "mean"), cqi=("cqi", "mean"),
        ovl=("rsrp_ovl", "sum"), n=("cqi", "size")).round(1)
    print(b[b.n > 0].to_string())

print()
print("=" * 190)
print("UL BLER vs SINR per rep — is the 5 m anomaly a link problem or something else?")
print("=" * 190)
u = m[m.direction == "UL"]
print(u[["location", "protocol", "rep", "snr", "ul_mcs", "ul_err", "ul_ok", "ul_nok",
         "phr", "ovl", "receiver_Mbps"]].to_string(index=False))
