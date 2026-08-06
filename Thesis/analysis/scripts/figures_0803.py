"""Figure: rx_gain is a per-distance trade-off, not a single correct value."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

SP = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")
FIG = Path(r"d:/Documents/Thesis/thesis/Thesis/analysis/figures")

C70, C60, C4G = "#2a78d6", "#eb6834", "#52514e"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e3e2dd"
plt.rcParams.update({
    "font.family": "serif", "font.size": 9,
    "axes.edgecolor": GRID, "axes.linewidth": 0.8, "axes.labelcolor": INK2,
    "axes.titlesize": 9.5, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "xtick.color": INK2, "ytick.color": INK2,
    "xtick.major.size": 0, "ytick.major.size": 0,
    "legend.frameon": False, "figure.dpi": 150, "savefig.bbox": "tight",
    "pdf.fonttype": 42})


def style(ax, ylabel=None):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_color(GRID)
    ax.set_axisbelow(True); ax.yaxis.grid(True, color=GRID, lw=0.7)
    if ylabel: ax.set_ylabel(ylabel)


MAP = {"Loc1_2m": "Location1", "Loc2_5m": "Location2", "Loc3_10m": "Location3"}
LOCS = ["Location1", "Location2", "Location3"]
LAB = ["2 m\nLOS", "5 m\npartition", "10 m\nwall"]

old = pd.read_csv(SP / "new_iperf_reps.csv"); old["location"] = old.location.map(MAP)
old["thr"] = np.where(old.direction == "UL", old.mean_Mbps_5s_on, old.receiver_Mbps)
new = pd.read_csv(SP / "aug03_reps_with_thr.csv")
om = pd.read_csv(SP / "new_steady_metrics.csv"); om["location"] = om.location.map(MAP)
nm = pd.read_csv(SP / "aug03_steady_metrics.csv")

o_thr = old[old.direction == "UL"].groupby("location")["thr"].mean().reindex(LOCS)
n_thr = new[(new.direction == "UL") & (new.location != "Location3_TDD")].groupby(
    "location")["thr"].mean().reindex(LOCS)
o_r = om[om.direction == "UL"].groupby("location").agg(
    snr=("pusch_snr_db", "mean"), bler=("ul_error_rate", "mean")).reindex(LOCS)
n_r = nm[(nm.direction == "UL") & (nm.location != "Location3_TDD")].groupby(
    "location").agg(snr=("pusch_snr_db", "mean"), bler=("ul_error_rate", "mean")).reindex(LOCS)
# 4G uplink baseline, mean of TCP and UDP per distance
BASE4G = {"Location1": 15.16, "Location2": 15.89, "Location3": 13.32}

fig, axes = plt.subplots(1, 3, figsize=(8.0, 3.0))
x, w = np.arange(3), 0.34

ax = axes[0]
for k, (vals, col, lbl) in enumerate([(o_thr, C70, "rx_gain 70"), (n_thr, C60, "rx_gain 60")]):
    bars = ax.bar(x + (k - 0.5) * w, vals, w * 0.9, color=col, edgecolor="white",
                  lw=1.3, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.8, f"{v:.1f}", ha="center",
                fontsize=6.8, color=INK)
for i, loc in enumerate(LOCS):
    ax.plot([i - 0.55, i + 0.55], [BASE4G[loc]] * 2, color=C4G, lw=1.4, ls="--", zorder=6)
ax.text(1.5, 34.5, "dashed = 4G uplink baseline", fontsize=6.6, color=C4G, ha="center")
ax.set_xticks(x, LAB, fontsize=7.5); ax.set_ylim(0, 38)
style(ax, ylabel="uplink throughput (Mb/s)")
ax.set_title("Throughput", loc="left")

ax = axes[1]
for k, (vals, col) in enumerate([(o_r.snr, C70), (n_r.snr, C60)]):
    bars = ax.bar(x + (k - 0.5) * w, vals, w * 0.9, color=col, edgecolor="white",
                  lw=1.3, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.6, f"{v:.1f}", ha="center",
                fontsize=6.8, color=INK)
ax.axhline(0, color=INK2, lw=0.9, ls=":")
ax.set_xticks(x, LAB, fontsize=7.5); ax.set_ylim(0, 30)
style(ax, ylabel="PUSCH SINR at gNB (dB)")
ax.set_title("Signal quality", loc="left")

ax = axes[2]
for k, (vals, col) in enumerate([(o_r.bler, C70), (n_r.bler, C60)]):
    bars = ax.bar(x + (k - 0.5) * w, vals, w * 0.9, color=col, edgecolor="white",
                  lw=1.3, zorder=3)
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.0f}%", ha="center",
                fontsize=6.8, color=INK)
ax.set_xticks(x, LAB, fontsize=7.5); ax.set_ylim(0, 62)
style(ax, ylabel="uplink block error rate")
ax.set_title("Errors", loc="left")

fig.legend(handles=[Line2D([], [], color=C70, lw=6, label="rx_gain 70  (2026-08-02)"),
                    Line2D([], [], color=C60, lw=6, label="rx_gain 60  (2026-08-03)")],
           loc="upper center", bbox_to_anchor=(0.5, 1.04), ncol=2, fontsize=8)
fig.suptitle("No single receiver gain serves the whole cell: 60 fixes 2 m and breaks 10 m",
             y=1.13, fontsize=10.5, fontweight="bold", color=INK)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig10_rxgain_tradeoff.{ext}")
plt.close(fig)
print("wrote", FIG / "fig10_rxgain_tradeoff.pdf")
