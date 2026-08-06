# What we have — inventory for drafting the Results chapter

Written 2026-08-04. A stock-take of every campaign, every derived result, and how far each
one can be pushed in the thesis. Companion to `FINDINGS.md`,
`FINDINGS_RERUN_2026-08-02.md`, `FINDINGS_RERUN_2026-08-03.md`.

---

## A. Raw data

| Campaign | Dates | Radio config | Runs | Traffic profile | Captured | Size |
|---|---|---|---|---|---|---|
| **`28-Jul/`** | 5G 2026-07-25, 4G 2026-07-28 | 5G: `rx_gain 70`, TDD 3 DL : 1 UL · 4G: bladeRF, Band 7 FDD, 10 MHz | **24** (2 tech × 3 loc × 2 proto × 2 dir, n=1) | iperf3 single stream | `gnb.log`/`enb.log` (`hex_max_size 64`), `trace.log` console metrics, MAC+NGAP pcaps (5G only) | 3.9 GB |
| **`02-Aug/`** | 2026-08-02 | 5G: `rx_gain 70`, TDD 2 DL : 2 UL | **39** (Loc1 12, Loc2 15, Loc3 12) | iperf3 `-P 8`, 20 s, UDP `-b 100M`/stream | `gnb.log` with `[METRICS]`, phone exports, server `test.json` (cumulative), pcaps | 3.7 GB |
| **`03-Aug/`** | 2026-08-03 | 5G: `rx_gain 60`, TDD 2 DL : 2 UL (+ 3 DL : 1 UL for the isolation run) | **36 + 3** | iperf3 `-P 8`, 20 s | `gnb1-3.log` with `[METRICS]`, phone exports, per-location server JSON, pcaps, **3 ping captures**, **`amf.log`** | 3.6 GB |

**Total: 102 measurement runs, ~11.2 GB.** All three share the same Open5GS core machine and
the same UE (Samsung Z Flip 5, CellularLab).

**Not yet exploited:** every MAC pcap (77 MB–1.1 GB each) and every NGAP pcap (2–9 KB each).
The NGAP ones are small and ideal for Wireshark screenshots in the walkthrough appendix.

---

## B. Derived results

Confidence key — **A** = solid, quantitative, defensible as-is · **B** = solid but needs a
stated caveat · **C** = suggestive, do not lead with it.

| # | Result | Headline numbers | Campaign | n | Conf. | Data / figure |
|---|---|---|---|---|---|---|
| 1 | 4G vs 5G throughput across 3 distances | 5G DL 1.0–2.6× of 4G; 5G UL 0.04–0.39× | 28-Jul | 1 | **B** | `summary_kpis.csv` · fig1, fig2 |
| 2 | **Uplink deficit decomposes exactly** | 2.5× TDD airtime × 8.7× link budget = 21.5× measured | 28-Jul | 1 | **A** | `active_samples.csv` |
| 3 | Uplink SINR / PHR vs distance | 4G flat +11.5…14.2 dB, PHR +12…+20 · 5G +10.7→−7.6 dB, PHR −2…−14 | 28-Jul | 1 | **A** | fig5 |
| 4 | **Uplink quality bounds downlink TCP** | 10 m TCP DL: 53.7 % PUSCH BLER, 10.3 Mb/s vs 27.7 UDP | 28-Jul | 1 | **A** | `phy_summary.csv` · fig3 |
| 5 | Connection stability | 9 RLFs (Jul) → 18 re-attaches (Aug-02) → **0** (Aug-03) | all | — | **A** | `event_summary.csv` |
| 6 | No incremental redundancy on UL HARQ | 100 % of PUSCH at `rv=0`; 60.5 % first-attempt decode at 10 m | 28-Jul | 1 | **A** | `harq_check.py` |
| 7 | **Software RAN real-time headroom** | PUSCH decode p99 460–560 µs vs 500 µs slot budget; 13 late/underrun events | 28-Jul | 1 | **A** | fig4 |
| 8 | Control-plane latency | 5G attach 360 ms vs 4G 166 ms; NG setup 9.5 vs 1.9 ms | 28-Jul | 1 | **A** | `control_plane.csv` · fig6 |
| 9 | Logging cost of continuous operation | 2.1 MB/s avg, 6.0 MB/s peak → ~7.5 GB/h; 57–77 % hex dumps | 28-Jul | — | **A** | — |
| 10 | **TDD rebalance = pure airtime trade** | DL measured/predicted 0.99 at 10 m, 1.14 at 2 m | 28-Jul vs 02-Aug | 1 vs 3 | **A** | fig7 |
| 11 | **Bufferbloat, root cause located** | RLC queue 6.17 MB, filled to 6.165 MB (99.9 %); RTT 0.4 → 6.5 s, 0 retransmissions | 02-Aug | 3 | **A** | `server_intervals.csv` · fig9 |
| 12 | **No single `rx_gain` serves the cell** | 70: 2 m 22 % BLER / 10 m 1 % · 60: 2 m 6 % / 10 m SINR 1.0 dB. −10 dB gain → −17 dB SINR at 10 m | 02 vs 03-Aug | 3 | **A** | fig8, fig10 |
| 13 | Best 5G result to date | 2 m at `rx_gain 60`: UL 26.8 TCP / 31.7 UDP Mb/s = **2× the 4G baseline** | 03-Aug | 3 | **A** | `aug03_reps_with_thr.csv` |
| 14 | **Unloaded latency** | Floor 15.7–16.0 ms at every distance; mean 25–28 ms; 0 % loss | 03-Aug | 30 echoes | **A** | `ping_summary.csv` · fig11 |
| 15 | Latency budget decomposition | ≈16 ms fixed + 0–19 ms wait for uplink grant (from the 1.2 ms/s sawtooth) | 03-Aug | 30 | **B** | fig11 |
| 16 | Idle vs loaded latency | 25–28 ms → 0.5–2.3 s, inflation ×35–81 | 02+03-Aug | 3 | **A** | fig11 |
| 17 | PHR tracks PRB allocation | Measured within 1.5 dB of −10·log₁₀(M_RB) across 1331 reports | 03-Aug | 1331 | **A** | `aug03_metrics.csv` |
| 18 | UDP uplink jitter | 6.1–7.6 ms @2 m · 17–35 @5 m · 87.6–115.3 @10 m | 03-Aug | 3 | **A** | `aug03_server_tests.csv` |
| 19 | Modulation ladder in use | 5G PDSCH 86–96 % 256QAM at 2–5 m; 4G reaches 256QAM 39 % at 2 m | 28-Jul | 1 | **A** | `phy_summary.csv` |
| 20 | Downlink PRB saturation | 4G 49.6/50, 5G 47–49/51 — DL limited by MCS+BLER, not scheduling | 28-Jul | 1 | **A** | `phy_summary.csv` |
| 21 | Open5GS/srsRAN interop rough edges | NGAP release/setup race (Jul); `DUPLICATED_PDU_SESSION_ID` + HTTP 500 on gNB restart (Aug-03) | 28-Jul, 03-Aug | — | **B** | `amf.log` |
| 22 | TDD isolation at 10 m | 3:1 gave 5.64 Mb/s vs 2:2's 3.50 — **inverted**, 13.4 dB SINR gap unexplained | 03-Aug | 3 | **C** | — |
| 23 | July→August 10 m uplink jump | +22 dB at same nominal placement and gain — no mechanism | 28-Jul vs 02-Aug | 1 vs 3 | **C** | — |

---

## C. Claims register

**Lead with these (A):** 2, 4, 7, 10, 11, 12, 13, 14, 16.
Those nine are the spine of a strong Results chapter — each is quantitative, mechanistically
explained, and traceable to raw data.

**Use, with the caveat stated:**

| Result | Required caveat |
|---|---|
| 1, 3, 19, 20 | 4G is n=1 and differs in band, bandwidth, duplexing, SDR and front end. Frame as *this 5G deployment vs this 4G deployment*. |
| 10 | The 08-02 campaign changed traffic profile (single-stream → `-P 8`) at the same time as the TDD pattern. TCP comparisons across campaigns are partly profile, not radio. |
| 15 | The ≈19 ms is inferred from the beat, not read from the gNB config. |
| 21 | Observed, not root-caused. |
| any PHR figure | Only comparable at equal PRB allocation (result 17). |

**Do not claim:**
- That the TDD rebalance recovered the uplink ~20× — airtime accounts for ~2×, the rest is unexplained (23).
- Any conclusion from the TDD isolation run — it ran at a gain where the 10 m uplink is broken (22).
- Anything from `02-Aug/Loc2_5m` — 18 re-attaches, one 0.00 Mb/s rep, unusable.

---

## D. Two data traps when re-reading the CSVs

1. **`receiver_Mbps` is 0.00 on the stalled 03-Aug 10 m uplink runs.** The iperf3 results
   exchange failed; the link actually carried ~3.5 Mb/s. Use sender-side figures there —
   `analyse_0803.py` already does.
2. **UDP `loss %` on downlink is meaningless.** `-b 100M -P 8` offers 800 Mb/s into a ~40 Mb/s
   link, so 83–89 % "loss" is the offered-load artefact. Report delivered rate instead.

---

## E. Gaps

| Gap | Cost to close | Blocks anything? |
|---|---|---|
| RLC queue resize not measured | ~15 min lab | No — but it converts a diagnosed problem into a demonstrated fix |
| TDD isolation confounded | ~10 min lab at `rx_gain 70` | No — report as inconclusive |
| Only `amf.log` captured; no `smf`/`upf`/`nrf`/`udm`/`udr`/`ausf` | `journalctl` over SSH | Only the full-NF startup walkthrough |
| MAC + NGAP pcaps unexploited | Desk work, Wireshark | No |
| `PLACEMENT.md` never written | Photos + rough distances exist | No — the floor plan supersedes it |
| No 4G repeats | Would need a 4G re-run | No — state n=1 |

---

## F. Figures currently available

`Thesis/analysis/figures/` — all as PDF (vector, for LaTeX) and PNG.

| | Figure | Shows |
|---|---|---|
| fig1 | Throughput 4G vs 5G | 2×2 small multiples, DL/UL × TCP/UDP |
| fig2 | Per-second time series | TCP vs UDP dynamics per distance |
| fig3 | Uplink BLER | The 53.7 % ACK-path failure |
| fig4 | PHY processing time | ECDF vs the 500 µs deadline |
| fig5 | Uplink SINR | Box plots, 4G flat vs 5G collapsing |
| fig6 | Control-plane latency | Stage-by-stage attach breakdown |
| fig7 | TDD rebalance | 4G / before / after, with min–max bars |
| fig8 | Overload evidence | Grants, SINR, BLER — the inversion |
| fig9 | Bufferbloat | RTT and in-flight data over 20 s |
| fig10 | rx_gain trade-off | 70 vs 60 across all three locations |
| fig11 | Unloaded latency | Ping sawtooth + idle-vs-loaded |

Treat these as drafts/inspiration — the underlying CSVs in `analysis/data/` are the durable
artefact and can be re-plotted in whatever style the final document uses.
