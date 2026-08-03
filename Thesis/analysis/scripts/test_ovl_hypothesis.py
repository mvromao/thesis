"""Is the reported uplink SINR trustworthy at high receive levels?

If the ADC is clipping at rx_gain 70, the measured SINR is inflated while the
constellation is actually damaged -> link adaptation picks too high an MCS ->
BLER rises *with* reported SINR instead of falling.
"""
import pandas as pd
import numpy as np

SP = r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad/"
pd.set_option("display.width", 220)

st = pd.read_csv(SP + "new_steady_metrics.csv")
ul = st[(st.direction == "UL") & st.pusch_snr_db.notna() & st.ul_error_rate.notna()].copy()

print("=" * 120)
print("Reported PUSCH SINR vs uplink BLER, per location (UL tests, steady state)")
print("=" * 120)
for loc, g in ul.groupby("location"):
    r = np.corrcoef(g.pusch_snr_db, g.ul_error_rate)[0, 1]
    print(f"\n{loc}:  n={len(g)}  corr(SINR, BLER) = {r:+.2f}")
    b = g.groupby(pd.cut(g.pusch_snr_db, [-10, 5, 10, 15, 20, 25, 35])).agg(
        n=("ul_error_rate", "size"), mean_BLER=("ul_error_rate", "mean"),
        mean_MCS=("ul_mcs", "mean"), mean_PHR=("last_phr", "mean"),
    ).round(1)
    print(b[b.n > 0].to_string())

print()
print("=" * 120)
print("The inversion, stated plainly: mean per location (UL tests)")
print("=" * 120)
t = ul.groupby("location").agg(
    reported_SINR=("pusch_snr_db", "mean"),
    chosen_MCS=("ul_mcs", "mean"),
    actual_BLER=("ul_error_rate", "mean"),
    PHR=("last_phr", "mean"),
    ovl_flags=("rsrp_ovl", "sum"),
    grants_ok=("ul_nof_ok", "mean"),
    grants_failed=("ul_nof_nok", "mean"),
).round(2)
t["grants_total"] = (t.grants_ok + t.grants_failed).round(0)
print(t.to_string())

print()
print("Every location is granted the full ~800 uplink slots/s the new TDD pattern allows.")
print("What differs is how many of them decode.")

print()
print("=" * 120)
print("Same check on the DOWNLINK tests (uplink carries only feedback + TCP ACKs)")
print("=" * 120)
dl = st[(st.direction == "DL") & st.pusch_snr_db.notna()].copy()
print(dl.groupby("location").agg(
    reported_SINR=("pusch_snr_db", "mean"), ul_MCS=("ul_mcs", "mean"),
    ul_BLER=("ul_error_rate", "mean"), cqi=("cqi", "mean"),
    dl_MCS=("dl_mcs", "mean"), dl_BLER=("dl_error_rate", "mean"),
    PHR=("last_phr", "mean"), ovl=("rsrp_ovl", "sum")).round(2).to_string())
