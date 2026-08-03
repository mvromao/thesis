"""Bufferbloat figure from the server-side iperf3 JSON."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

SP = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")
FIG = Path(r"d:/Documents/Thesis/thesis/Thesis/analysis/figures")

REP = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e3e2dd"
plt.rcParams.update({
    "font.family": "serif", "font.size": 9,
    "axes.edgecolor": GRID, "axes.linewidth": 0.8, "axes.labelcolor": INK2,
    "axes.titlesize": 9.5, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "xtick.color": INK2, "ytick.color": INK2,
    "xtick.major.size": 0, "ytick.major.size": 0,
    "legend.frameon": False, "figure.dpi": 150, "savefig.bbox": "tight",
    "pdf.fonttype": 42})


def style(ax, ylabel=None, xlabel=None):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_color(GRID)
    ax.set_axisbelow(True); ax.yaxis.grid(True, color=GRID, lw=0.7)
    if ylabel: ax.set_ylabel(ylabel)
    if xlabel: ax.set_xlabel(xlabel)


iv = pd.read_csv(SP / "server_intervals.csv")
iv = iv[iv.location != "warm-up"]
iv = iv[iv.sec < 20]                      # drop the final partial interval
LOCS = [("Loc1_2m", "2 m, line of sight"), ("Loc2_5m", "5 m, partition"),
        ("Loc3_10m", "10 m, concrete wall")]

fig, axes = plt.subplots(2, 3, figsize=(7.6, 4.4), sharex=True)
for j, (loc, title) in enumerate(LOCS):
    s = iv[iv.location == loc]
    cookies = list(dict.fromkeys(s.cookie))
    # ---- row 0: round-trip time
    ax = axes[0, j]
    for k, c in enumerate(cookies):
        g = s[s.cookie == c].sort_values("sec")
        ax.plot(g.sec, g.rtt_ms, color=REP[k % 4], lw=1.5, label=f"rep {k+1}")
    ax.axhline(100, color=INK2, ls=":", lw=0.9)
    if j == 2:
        ax.text(19.4, 112, "100 ms", fontsize=6.6, color=INK2, ha="right")
    ax.set_yscale("log")
    ax.set_ylim(40, 9000)
    ax.set_yticks([50, 100, 500, 1000, 5000], ["50", "100", "500", "1000", "5000"])
    ax.set_title(title, loc="left")
    style(ax, ylabel="TCP round-trip time (ms)" if j == 0 else None)
    # ---- row 1: congestion window = data in flight
    ax = axes[1, j]
    for k, c in enumerate(cookies):
        g = s[s.cookie == c].sort_values("sec")
        ax.plot(g.sec, g.cwnd_kB / 1e3, color=REP[k % 4], lw=1.5)
    ax.set_ylim(0, 8.2)
    style(ax, ylabel="data in flight (MB)" if j == 0 else None,
          xlabel="seconds into transfer")

fig.legend(handles=[Line2D([], [], color=REP[k], lw=2, label=f"rep {k+1}") for k in range(4)],
           loc="upper center", bbox_to_anchor=(0.5, 1.005), ncol=4, fontsize=7.5)
fig.suptitle("Downlink TCP fills a multi-megabyte queue inside the gNB and never sees a loss",
             y=1.06, fontsize=10.5, fontweight="bold", color=INK)
fig.text(0.5, -0.04,
         "8 parallel streams, 20 s. At 10 m the round-trip time grows from 0.4 s to 6.5 s "
         "with 0–3 retransmissions in the whole run.",
         ha="center", fontsize=7, color=INK2)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig9_bufferbloat.{ext}")
plt.close(fig)
print("wrote", FIG / "fig9_bufferbloat.pdf")

# ---------------------------------------------------------------- summary table
t = pd.read_csv(SP / "server_tests.csv")
t = t[(t.location != "warm-up") & (t.protocol == "TCP") & (t.direction == "DL")]
peak_inflight = iv.groupby("location")["cwnd_kB"].max() / 1e3
summ = t.groupby("location").agg(
    Mbps=("server_Mbps", "mean"), mean_rtt_ms=("mean_rtt_ms", "mean"),
    min_rtt_ms=("min_rtt_ms", "min"), max_rtt_ms=("max_rtt_ms", "max"),
    retx=("retransmits", "mean"),
).round(1)
summ["peak_inflight_MB"] = peak_inflight.round(2)
summ["queue_seconds"] = (summ.peak_inflight_MB * 8 / summ.Mbps).round(1)
print()
print(summ.to_string())
