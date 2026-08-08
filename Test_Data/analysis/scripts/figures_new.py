"""Figures for the 2026-08-02 re-run campaign."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

SP = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")
FIG = Path(r"d:/Documents/Thesis/thesis/Thesis/analysis/figures")

C4G, COLD, CNEW = "#2a78d6", "#eb6834", "#1baf7a"
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


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{name}.{ext}")
    plt.close(fig)
    print("wrote", FIG / f"{name}.pdf")


DIST = [2, 5, 10]
reps = pd.read_csv(SP / "new_iperf_reps.csv")
reps["dist"] = reps.location.map({"Loc1_2m": 2, "Loc2_5m": 5, "Loc3_10m": 10})
old = pd.read_csv(SP / "active_samples.csv")
old["load"] = np.where(old.direction == "DL", old.dl_brate, old.ul_brate)
o5 = old[old.tech == "5G"].groupby(["distance_m", "protocol", "direction"])["load"].mean() / 1e6
o4 = old[old.tech == "4G"].groupby(["distance_m", "protocol", "direction"])["load"].mean() / 1e6
new = reps.groupby(["dist", "protocol", "direction"])["receiver_Mbps"].agg(["mean", "min", "max"])

# ------------------------------------------------------------------ Figure 7
fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.0), sharex=True)
for i, d in enumerate(["DL", "UL"]):
    for j, p in enumerate(["TCP", "UDP"]):
        ax = axes[i, j]
        x, w = np.arange(3), 0.26
        for k, (lbl, col) in enumerate([("4G", C4G), ("old", COLD), ("new", CNEW)]):
            vals, lo, hi = [], [], []
            for dd in DIST:
                if lbl == "4G":
                    v = o4.get((dd, p, d), np.nan); l = h = v
                elif lbl == "old":
                    v = o5.get((dd, p, d), np.nan); l = h = v
                else:
                    row = new.loc[(dd, p, d)]
                    v, l, h = row["mean"], row["min"], row["max"]
                vals.append(v); lo.append(v - l); hi.append(h - v)
            bars = ax.bar(x + (k - 1) * w, vals, w * 0.9, color=col,
                          edgecolor="white", linewidth=1.2, zorder=3)
            if lbl == "new":
                ax.errorbar(x + (k - 1) * w, vals, yerr=[lo, hi], fmt="none",
                            ecolor=INK2, elinewidth=1.0, capsize=2.5, zorder=4)
            for b, v in zip(bars, vals):
                txt = f"{v:.1f}" if v < 10 else f"{v:.0f}"
                ax.text(b.get_x() + b.get_width() / 2, v + 1.2, txt,
                        ha="center", va="bottom", fontsize=6.6, color=INK)
        ax.set_xticks(x, ["2 m\nLOS", "5 m\npartition", "10 m\nconcrete"])
        ax.set_ylim(0, 58)
        ax.set_title(f"{d} · {p}", loc="left")
        style(ax, ylabel="Mb/s" if j == 0 else None)
        if d == "UL":
            ax.annotate("5 m unusable —\nUE re-attached 18×", xy=(1.26, 9),
                        xytext=(0.30, 27), fontsize=6.4, color=INK2,
                        arrowprops=dict(arrowstyle="->", color=INK2, lw=0.8))
fig.legend(handles=[Line2D([], [], color=C4G, lw=6, label="4G baseline (unchanged, n=1)"),
                    Line2D([], [], color=COLD, lw=6, label="5G before (3 DL : 1 UL, n=1)"),
                    Line2D([], [], color=CNEW, lw=6, label="5G after (2 DL : 2 UL, n=3–4)")],
           loc="upper center", bbox_to_anchor=(0.5, 1.06), ncol=3, fontsize=8)
fig.suptitle("Effect of re-balancing the TDD pattern: uplink recovered, downlink traded away",
             y=1.11, fontsize=10.5, fontweight="bold", color=INK)
fig.tight_layout()
save(fig, "fig7_tdd_rebalance")

# ------------------------------------------------------------------ Figure 8
st = pd.read_csv(SP / "new_steady_metrics.csv")
ul = st[st.direction == "UL"]
agg = ul.groupby("location").agg(
    snr=("pusch_snr_db", "mean"), mcs=("ul_mcs", "mean"),
    bler=("ul_error_rate", "mean"), ok=("ul_nof_ok", "mean"),
    nok=("ul_nof_nok", "mean"), phr=("last_phr", "mean")).reindex(
    ["Loc1_2m", "Loc2_5m", "Loc3_10m"])
labels = ["2 m\nline of sight", "5 m\npartition", "10 m\nconcrete wall"]

fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.9))
x = np.arange(3)

ax = axes[0]
ax.bar(x, agg.ok, 0.6, color=CNEW, edgecolor="white", lw=1.4, zorder=3, label="decoded")
ax.bar(x, agg.nok, 0.6, bottom=agg.ok, color="#e34948", edgecolor="white",
       lw=1.4, zorder=3, label="failed CRC")
for i, (o, n) in enumerate(zip(agg.ok, agg.nok)):
    ax.text(i, o / 2, f"{o:.0f}", ha="center", va="center", fontsize=7,
            color="white", fontweight="bold")
ax.axhline(800, color=INK, lw=1.0, ls="--", zorder=5)
ax.text(2.45, 815, "800/s TDD ceiling", ha="right", fontsize=6.6, color=INK)
ax.set_xticks(x, labels, fontsize=7.5)
ax.set_ylim(0, 900)
style(ax, ylabel="uplink transmissions per second")
ax.set_title("Every location gets the\nsame number of grants", loc="left", fontsize=9)
ax.legend(fontsize=7, loc="lower left")

ax = axes[1]
b = ax.bar(x, agg.snr, 0.6, color="#2a78d6", edgecolor="white", lw=1.4, zorder=3)
for i, v in enumerate(agg.snr):
    ax.text(i, v + 0.5, f"{v:.1f} dB", ha="center", fontsize=7, color=INK)
ax.set_xticks(x, labels, fontsize=7.5)
ax.set_ylim(0, 26)
style(ax, ylabel="reported PUSCH SINR (dB)")
ax.set_title("The gNB reports good\nsignal quality everywhere", loc="left", fontsize=9)

ax = axes[2]
b = ax.bar(x, agg.bler, 0.6, color="#e34948", edgecolor="white", lw=1.4, zorder=3)
for i, (v, m) in enumerate(zip(agg.bler, agg.mcs)):
    ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", fontsize=7.5, color=INK,
            fontweight="bold")
    ax.text(i, 2, f"MCS {m:.0f}", ha="center", fontsize=6.8, color="white")
ax.set_xticks(x, labels, fontsize=7.5)
ax.set_ylim(0, 62)
style(ax, ylabel="uplink block error rate")
ax.set_title("…but only the far point\nactually decodes", loc="left", fontsize=9)

fig.suptitle("Close to the radio, the reported SINR is optimistic and link adaptation over-reaches",
             y=1.04, fontsize=10.5, fontweight="bold", color=INK)
fig.tight_layout()
save(fig, "fig8_overload_evidence")
