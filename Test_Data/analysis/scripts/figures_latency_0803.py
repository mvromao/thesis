"""Unloaded latency, and what the RLC queue does to it under load."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

SP = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")
FIG = Path(r"d:/Documents/Thesis/thesis/Thesis/analysis/figures")

C = ["#2a78d6", "#eb6834", "#1baf7a"]
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


ser = pd.read_csv(SP / "ping_series.csv")
summ = pd.read_csv(SP / "ping_summary.csv")
LOCS = ["2 m, line of sight", "5 m, partition", "10 m, concrete wall"]

fig, axes = plt.subplots(1, 2, figsize=(7.8, 3.0),
                         gridspec_kw={"width_ratios": [1.45, 1]})

ax = axes[0]
for i, loc in enumerate(LOCS):
    g = ser[ser.location == loc].sort_values("seq")
    ax.plot(g.seq, g.rtt_ms, color=C[i], lw=1.4, marker="o", ms=2.6, label=loc)
floor = summ["min"].min()
ax.axhline(floor, color=INK, lw=1.0, ls="--", zorder=5)
ax.text(30.4, floor - 2.2, f"floor {floor:.1f} ms", fontsize=6.8, color=INK, ha="right")
ax.annotate("", xy=(0.75, 16.0), xytext=(0.75, 35.0),
            arrowprops=dict(arrowstyle="<->", color=INK2, lw=0.9))
ax.set_xlim(-1.6, 31); ax.set_ylim(10, 54)
style(ax, ylabel="round-trip time (ms)", xlabel="ICMP echo number (1 per second)")
ax.set_title("Unloaded: a 16 ms floor plus a sawtooth", loc="left")
ax.legend(fontsize=7, loc="upper right", ncol=1)

ax = axes[1]
loaded = {"2 m, line of sight": 870.9, "5 m, partition": 1120.3,
          "10 m, concrete wall": 2124.8}
x, w = np.arange(3), 0.36
un = [summ[summ.location == l]["mean"].iloc[0] for l in LOCS]
ld = [loaded[l] for l in LOCS]
b1 = ax.bar(x - w / 2, un, w * 0.9, color="#1baf7a", edgecolor="white", lw=1.3, zorder=3)
b2 = ax.bar(x + w / 2, ld, w * 0.9, color="#e34948", edgecolor="white", lw=1.3, zorder=3)
for b, v in zip(b1, un):
    ax.text(b.get_x() + b.get_width() / 2, v * 1.15, f"{v:.0f}", ha="center",
            fontsize=7, color=INK)
for b, v in zip(b2, ld):
    ax.text(b.get_x() + b.get_width() / 2, v * 1.15, f"{v:.0f}", ha="center",
            fontsize=7, color=INK)
ax.set_yscale("log")
ax.set_ylim(8, 6000)
ax.set_yticks([10, 100, 1000], ["10", "100", "1000"])
ax.set_xticks(x, ["2 m\nLOS", "5 m\npartition", "10 m\nwall"], fontsize=7.5)
style(ax, ylabel="mean round-trip time (ms)")
ax.set_title("…and what a saturating\ndownload does to it", loc="left")
ax.legend(handles=[Line2D([], [], color="#1baf7a", lw=6, label="idle"),
                   Line2D([], [], color="#e34948", lw=6, label="TCP download")],
          fontsize=7, loc="upper left")

fig.suptitle("The testbed's latency is fine until the 6.17 MB downlink queue fills",
             y=1.05, fontsize=10.5, fontweight="bold", color=INK)
fig.text(0.02, -0.07,
         "Left: the arrow marks the ≈19 ms window the round-trip time sweeps. The 1 s ping "
         "interval drifts 1.2 ms per packet against a periodic uplink\nscheduling "
         "opportunity, so each echo waits a different fraction of that cycle. "
         "Distance changes the floor by 0.3 ms; the queue changes the mean by 35–81×.",
         ha="left", fontsize=6.8, color=INK2)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(FIG / f"fig11_unloaded_latency.{ext}")
plt.close(fig)
print("wrote", FIG / "fig11_unloaded_latency.pdf")
