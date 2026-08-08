"""Thesis figures from the srsRAN 4G/5G measurement campaign."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

SP = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")
FIG = Path(r"d:/Documents/Thesis/thesis/Thesis/analysis/figures")
FIG.mkdir(parents=True, exist_ok=True)

C4G, C5G, C3 = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e3e2dd"

plt.rcParams.update({
    "font.family": "serif", "font.size": 9,
    "axes.edgecolor": GRID, "axes.linewidth": 0.8, "axes.labelcolor": INK2,
    "axes.titlesize": 9.5, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "xtick.color": INK2, "ytick.color": INK2,
    "xtick.major.size": 0, "ytick.major.size": 0,
    "legend.frameon": False, "figure.dpi": 150, "savefig.bbox": "tight",
    "pdf.fonttype": 42,
})


def style(ax, ylabel=None, xlabel=None, ygrid=True):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    if ygrid:
        ax.set_axisbelow(True)
        ax.yaxis.grid(True, color=GRID, lw=0.7)
    if ylabel:
        ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{name}.{ext}")
    plt.close(fig)
    print("wrote", FIG / f"{name}.pdf")


act = pd.read_csv(SP / "active_samples.csv")
tidy = pd.read_csv(SP / "trace_tidy.csv")
phy = pd.DataFrame(json.loads((SP / "phy.json").read_text()))
phy["dist"] = phy.location.str.extract(r"(\d+)m$").astype(int)

DIST = [2, 5, 10]

# ---------------------------------------------------------------- Figure 1
# Mean user-plane throughput: 2x2 small multiples (direction x protocol)
fig, axes = plt.subplots(2, 2, figsize=(6.9, 4.6), sharex=True)
for i, d in enumerate(["DL", "UL"]):
    for j, p in enumerate(["TCP", "UDP"]):
        ax = axes[i, j]
        sub = act[(act.direction == d) & (act.protocol == p)]
        w, x = 0.36, np.arange(3)
        for k, (tech, col) in enumerate([("4G", C4G), ("5G", C5G)]):
            vals = [sub[(sub.tech == tech) & (sub.distance_m == dd)].load_brate.mean() / 1e6
                    for dd in DIST]
            bars = ax.bar(x + (k - 0.5) * w, vals, w * 0.92, color=col,
                          edgecolor="white", linewidth=1.4, zorder=3)
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v + 1.6, f"{v:.1f}",
                        ha="center", va="bottom", fontsize=7.2, color=INK)
        ax.set_xticks(x, [f"{v} m" for v in DIST])
        ax.set_ylim(0, 60)
        ax.set_title(f"{d} · {p}", loc="left")
        style(ax, ylabel="Mb/s" if j == 0 else None)
fig.legend(handles=[Line2D([], [], color=C4G, lw=6, label="4G  (10 MHz FDD, 2.6 GHz)"),
                    Line2D([], [], color=C5G, lw=6, label="5G SA  (20 MHz TDD, 3.41 GHz)")],
           loc="upper center", bbox_to_anchor=(0.5, 1.07), ncol=2)
fig.suptitle("Mean application throughput over the iperf3 steady-state window",
             y=1.13, fontsize=10.5, fontweight="bold", color=INK)
fig.text(0.5, -0.06, "2 m line of sight · 5 m through an office partition · "
         "10 m through a concrete wall.  Single run per cell.",
         ha="center", fontsize=6.8, color=INK2)
save(fig, "fig1_throughput")

# ---------------------------------------------------------------- Figure 2
# Per-second throughput time series - the TCP collapse story
fig, axes = plt.subplots(2, 3, figsize=(7.6, 4.0), sharey="row")
for i, d in enumerate(["DL", "UL"]):
    for j, dd in enumerate(DIST):
        ax = axes[i, j]
        for tech, col in [("4G", C4G), ("5G", C5G)]:
            for p, ls in [("TCP", "-"), ("UDP", "--")]:
                s = tidy[(tidy.tech == tech) & (tidy.distance_m == dd) &
                         (tidy.direction == d) & (tidy.protocol == p)]
                y = (s.dl_brate if d == "DL" else s.ul_brate).values / 1e6
                if len(y) == 0:
                    continue
                lo = np.argmax(y >= 0.2 * np.nanmax(y))
                y = y[lo:lo + 30]
                ax.plot(np.arange(len(y)), y, ls, color=col, lw=1.6,
                        alpha=1.0 if p == "TCP" else 0.75)
        ax.set_title(f"{d} @ {dd} m", loc="left")
        style(ax, ylabel="Mb/s" if j == 0 else None,
              xlabel="seconds into transfer" if i == 1 else None)
fig.legend(handles=[Line2D([], [], color=C4G, lw=2, label="4G"),
                    Line2D([], [], color=C5G, lw=2, label="5G"),
                    Line2D([], [], color=INK2, lw=2, ls="-", label="TCP"),
                    Line2D([], [], color=INK2, lw=2, ls="--", label="UDP")],
           loc="upper center", bbox_to_anchor=(0.5, 1.06), ncol=4)
fig.suptitle("Per-second throughput during the transfer", y=1.12,
             fontsize=10.5, fontweight="bold", color=INK)
fig.tight_layout()
save(fig, "fig2_timeseries")

# ---------------------------------------------------------------- Figure 3
# Uplink first-transmission BLER measured at the base station
fig, axes = plt.subplots(1, 2, figsize=(6.9, 2.9), sharey=True)
for j, d in enumerate(["DL", "UL"]):
    ax = axes[j]
    w, x = 0.36, np.arange(3)
    for k, (tech, col) in enumerate([("4G", C4G), ("5G", C5G)]):
        vals = [phy[(phy.tech == tech) & (phy.dist == dd) &
                    (phy.direction == d)].ul_bler_pct.mean() for dd in DIST]
        bars = ax.bar(x + (k - 0.5) * w, vals, w * 0.92, color=col,
                      edgecolor="white", linewidth=1.4, zorder=3)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.9, f"{v:.1f}%",
                    ha="center", va="bottom", fontsize=7.2, color=INK)
    ax.axhline(10, color=INK2, lw=0.9, ls=":", zorder=2)
    if j == 1:
        ax.text(-0.45, 11.2, "10 % link-adaptation target", fontsize=6.8,
                color=INK2, ha="left")
    ax.set_xticks(x, [f"{v} m" for v in DIST])
    ax.set_title(f"during {d} transfer", loc="left")
    style(ax, ylabel="PUSCH first-transmission BLER" if j == 0 else None)
    ax.set_ylim(0, 45)
fig.legend(handles=[Line2D([], [], color=C4G, lw=6, label="4G"),
                    Line2D([], [], color=C5G, lw=6, label="5G SA")],
           loc="upper center", bbox_to_anchor=(0.5, 1.10), ncol=2)
fig.suptitle("Uplink block errors at the base station (mean of TCP and UDP runs)",
             y=1.17, fontsize=10.5, fontweight="bold", color=INK)
save(fig, "fig3_ul_bler")

# ---------------------------------------------------------------- Figure 4
# PHY processing time vs the real-time slot budget
fig, axes = plt.subplots(1, 2, figsize=(6.9, 3.0))
for j, (tech, budget, col, label) in enumerate(
        [("5G", 500, C5G, "5G  ·  0.5 ms slot (30 kHz SCS)"),
         ("4G", 1000, C4G, "4G  ·  1 ms subframe")]):
    ax = axes[j]
    sub = phy[phy.tech == tech]
    for _, r in sub.iterrows():
        pts = [(p, r.get(f"pusch_proc_us_p{p}".replace(".", "_")))
               for p in (1, 5, 25, 50, 75, 95, 99, "99_9")]
        xs = [r[f"pusch_proc_us_p{p}"] for p in (1, 5, 25, 50, 75, 95, 99, "99_9")]
        ys = [1, 5, 25, 50, 75, 95, 99, 99.9]
        ax.plot(xs, ys, color=col, lw=1.0, alpha=0.45)
    ax.axvline(budget, color=INK, lw=1.2, ls="--", zorder=5)
    ax.text(budget * 0.97, 20, f"{budget} µs deadline", rotation=90,
            ha="right", va="center", fontsize=7.2, color=INK)
    ax.set_xlim(0, 1100)
    ax.set_ylim(0, 102)
    ax.set_title(label, loc="left")
    style(ax, ylabel="percentile of transmissions" if j == 0 else None,
          xlabel="PUSCH decode time on host CPU (µs)")
fig.suptitle("Software base station: PHY processing time against the real-time deadline",
             y=1.06, fontsize=10.5, fontweight="bold", color=INK)
fig.tight_layout()
save(fig, "fig4_processing_time")

# ---------------------------------------------------------------- Figure 5
# Uplink SINR at the base station
fig, ax = plt.subplots(figsize=(6.9, 3.0))
pos, labels, colors = [], [], []
p = 0
for dd in DIST:
    for tech, col in [("4G", C4G), ("5G", C5G)]:
        r = phy[(phy.tech == tech) & (phy.dist == dd)]
        stats = [{
            "med": r.pusch_sinr_p50.mean(),
            "q1": r.pusch_sinr_p25.mean(), "q3": r.pusch_sinr_p75.mean(),
            "whislo": r.pusch_sinr_p5.mean(), "whishi": r.pusch_sinr_p95.mean(),
            "fliers": []}]
        bp = ax.bxp(stats, positions=[p], widths=0.55, showfliers=False,
                    patch_artist=True, manage_ticks=False)
        for b in bp["boxes"]:
            b.set(facecolor=col, edgecolor="white", lw=1.2)
        for part in ("whiskers", "caps"):
            for it in bp[part]:
                it.set(color=col, lw=1.2)
        for m in bp["medians"]:
            m.set(color="white", lw=1.4)
        pos.append(p); labels.append(tech); colors.append(col)
        p += 1
    p += 0.8
ax.axhline(0, color=INK2, lw=0.9, ls=":")
ax.set_xticks(pos, labels)
ax.set_ylim(-24, 24)
for i, (dd, obs) in enumerate(zip(DIST, ["LOS", "partition", "concrete wall"])):
    ax.text(pos[i * 2] + 0.5, -30, f"{dd} m · {obs}", ha="center", fontsize=8.5,
            color=INK, fontweight="bold")
style(ax, ylabel="PUSCH SINR at base station (dB)")
ax.set_title("Uplink quality holds across all locations in 4G but collapses in 5G",
             loc="left", fontsize=10.5)
fig.text(0.5, -0.13, "box = p25–p75, whiskers = p5–p95, averaged over the four runs per location.  "
         "The 5G handset was transmit-power capped (pcg_p_nr_fr1 = −15 dBm).",
         ha="center", fontsize=6.8, color=INK2)
save(fig, "fig5_ul_sinr")

# ---------------------------------------------------------------- Figure 6
# Control-plane: how long the UE takes to get a usable data bearer
cp = pd.read_csv(SP / "control_plane.csv")
cp = cp[cp.n_prach == 1]           # single-attempt attaches only
stages = [("rrc_setup_ms", "RRC connection setup"),
          ("security_ms", "AS security mode"),
          ("ics_ms", "Initial context setup"),
          ("pdu_session_ms", "PDU session / E-RAB setup")]
fig, ax = plt.subplots(figsize=(6.9, 2.7))
y, ticks, lab = 0, [], []
for tech, col in [("4G", C4G), ("5G", C5G)]:
    s = cp[cp.tech == tech]
    for k, (c, name) in enumerate(stages):
        # in 4G the E-RAB is set up inside InitialContextSetup - no separate stage
        if tech == "4G" and c == "pdu_session_ms":
            continue
        v = s[c].mean()
        ax.barh(y, v, 0.62, color=col, edgecolor="white", lw=1.2, zorder=3)
        ax.text(v + 3, y, f"{v:.0f} ms", va="center", fontsize=7.4, color=INK)
        ticks.append(y)
        lab.append(name + (" (E-RAB included)" if tech == "4G" and
                           c == "ics_ms" else ""))
        y -= 1
    y -= 0.7
ax.set_yticks(ticks, lab, fontsize=8)
ax.invert_yaxis()
style(ax, xlabel="mean duration (ms)", ygrid=False)
ax.xaxis.grid(True, color=GRID, lw=0.7); ax.set_axisbelow(True)
tot4 = cp[cp.tech == "4G"].total_attach_ms.mean()
tot5 = cp[cp.tech == "5G"].total_attach_ms.mean()
ax.set_xlim(0, 130)
ax.set_title(f"Connection establishment: 4G {tot4:.0f} ms vs 5G SA {tot5:.0f} ms end-to-end",
             loc="left", fontsize=10.5, pad=16)
ax.legend(handles=[Line2D([], [], color=C4G, lw=6, label="4G (S1AP / EPC)"),
                   Line2D([], [], color=C5G, lw=6, label="5G SA (NGAP / 5GC)")],
          loc="lower right", ncol=1, fontsize=8)
save(fig, "fig6_control_plane")
print("\nall figures written to", FIG)
