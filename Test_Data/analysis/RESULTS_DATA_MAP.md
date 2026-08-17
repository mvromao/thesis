# Results chapter — what to look for, and what to compare against what

Written 2026-08-17. Companion to `DATA_INVENTORY.md` (which is organised by
*campaign*) and to `6 - Results.tex` (which is organised by *argument*). This
file is the bridge: one entry per section stub in the chapter, naming the exact
file and column, the comparison axis, and the caveat that has to be stated.

Everything below comes from `data_v2/`, rebuilt from raw by the pipeline in
`pipeline/`. **All 115 checked values reproduce the pre-rebuild numbers exactly**
(`python -m pipeline.compare_baseline` → `ok=115, diff=0`), so numbers already
written into FINDINGS*.md remain citable.

---

## How to regenerate everything

```
cd Test_Data/analysis
python -m pipeline.extract --all --jobs 4      # 6.56 GB of logs -> 809 KB, ~105 s
python -m pipeline.build_tables                # -> data_v2/
python -m pipeline.compare_baseline            # regression gate vs data/
```

Pure standard library — no pandas, no pyarrow, no matplotlib.

Two reading aids:

```
python -m pipeline.to_excel     # data_v2/tables.xlsx - frozen header, one sheet per table
python -m pipeline.unpack       # extracted_csv/ - plain CSV copy of the .gz tree
```

`COLUMNS.md` defines every column in every table.

### Why stage 1 exists

`[METRICS ]` lines are **0.02–0.08 %** of a gNB log. Separating them from
everything else reduces the corpus by ~8,100× with no loss of measurement:

| | |
|---|---|
| 31 stack logs, raw | **6.56 GB** |
| `extracted/`, all runs | **809 KB** |
| full extraction time | 105 s (4 workers) |

Everything downstream reads `extracted/`, never a raw log again.

---

## The registry, and two naming traps it encodes

`pipeline/paths.py` resolves 31 **log units** (one streaming pass each) and
102 **repetitions** (the key for every results table).

1. **Location B is 6 m, not 5 m.** Folders say `Loc2_5m`/`Location2` and the old
   CSVs say "5 m"; that was a nominal figure from before the room was surveyed.
   `distance_m` carries the tape-measured value. Locations are A/B/C throughout,
   matching `tab:test-locations`.
2. **`1 - 28-Jul/**/enb_metrics.csv` is empty** — it contains only `#eof`. It
   looks like a data source and is not one.

### Provenance, read from the logs themselves (not from folder names)

| Unit | Round | TDD | `rx_gain` | `tx_gain` |
|---|---|---|---|---|
| `R1_5G_*` | 1 | 3DL:1UL | 70 | 89.75 |
| `R2_5G_*` | 2 | 2DL:2UL | 70 | 89.75 |
| `R3_5G_*` | 3 | 2DL:2UL | **60** | 89.75 |
| `R3_5G_C_TDD31` | 3 | **3DL:1UL** | **60** | 89.75 |

The 4G rows are blank on gain and band on purpose: **srsenb prints no
configuration at all**, only `nof_prb=50`. Those values must be cited from
`files/enb.conf`, not inferred. (This same "absence is evidence" property of the
5G dump is what disproved the `pcg_p_nr_fr1` power-cap claim.)

---

## Section-by-section

### §1 Throughput overview — 4G baseline vs the three 5G rounds

- **Compare:** `mean_Mbps` per (round × location × protocol × direction), as a
  R1→R2→R3 progression, plus the 5G/4G ratio per cell.
- **Read:** `data_v2/throughput_summary.csv` (49 rows) · per-rep detail in
  `data_v2/reps.csv` (102 rows).
- **Verified anchors:** 4G A/TCP/DL 26.05 · 5G R1 C/TCP/UL 0.58 vs 4G 11.83 =
  **20.4× worse** · R3 A/TCP/UL 25.23 vs 4G 12.68 = **1.99×**, i.e. the "2× the
  4G baseline" claim is exact.
- **Caveat:** 4G is n=1, and differs in band, bandwidth, duplexing, SDR *and*
  front end (it has an LNA the 5G rig lacks). Frame as *this 5G deployment vs
  this 4G deployment*. Round 2 also changed the traffic profile (single stream →
  `-P 8`) at the same time as the TDD pattern, so cross-round TCP differences are
  partly profile, not radio.
- **Exclude:** Round 2 Location B — 4 reps, sd 7.2 Mb/s on TCP DL, 18 re-attaches.

### §2 Uplink airtime / TDD decomposition — **now measured, not inferred**

- **Compare:** where uplink resource blocks actually land within the TDD period,
  at 2DL:2UL vs 3DL:1UL.
- **Read:** `data_v2/tdd_airtime.csv`, columns `pusch_rb_slot0..4`.
- **What it shows:** uplink PRBs occupy **only slots 3 and 4** under 2DL:2UL, and
  **only slot 4** under 3DL:1UL. The airtime ceiling is visible directly in the
  slot structure rather than inferred from counting grants per second.
- **This is new.** `Scheduler cell` metrics were never parsed before; §2
  previously rested on Round 1 grant-counting alone.
- **Caveat:** `ul_rb_share_measured` reflects the *traffic mix* of the session as
  well as the pattern (the TDD31 session ran TCP uplink only, so its 0.96 is not
  a property of the 3:1 pattern). Use the per-slot columns, not that ratio.
- **Report the isolation run as inconclusive:** `R3_5G_C_TDD31` gives 3.65 Mb/s
  vs 2.77 for 2:2 — inverted — but its uplink SINR is 14.41 dB against 1.95 dB
  for the 2:2 run at the same location. A 12.5 dB gap confounds it. Flag "redo at
  `rx_gain` 70" as future work.

### §3 Uplink quality vs distance, and the `rx_gain` trade-off

- **Compare:** `pusch_snr_db` and `last_phr_db` against distance, at rx_gain 70
  (R2) vs 60 (R3); plus receiver-overload incidence.
- **Read:** `throughput_summary.csv` (`pusch_snr_db`, `last_phr_db`,
  `rsrp_ovl_share`) · per-second detail in
  `extracted/<unit>/metrics_ue.csv.gz` (`rsrp_ovl` flag).
- **Overload evidence:** `pusch_rsrp_db=ovl` reports — R2 A **28**, R2 B 12,
  R2 C 0; R3 A **3**, R3 B 0, R3 C 0. Overload appears only close in, and only at
  gain 70. The pipeline keeps `ovl` distinct from missing data, since it means
  "front end saturated", not "no reading".
- **The citable sentence** (from `FINDINGS_RERUN_2026-08-03.md`): *rx_gain 70 is
  correct at 10 m and overloads at 2 m; rx_gain 60 is correct at 2 m and
  desensitises at 10 m — no single value works.* The table backs both halves:
  C/TCP/UL SINR 18.0 dB at gain 70 → 1.95 dB at gain 60.
- **Caveat — PHR is only comparable at equal PRB allocation.** `last_phr_db`
  contains a −10·log₁₀(M_RB) term, so a wider grant lowers PHR with no change in
  radio conditions; this is what the "PHR anomaly" turned out to be. Use
  `ul_prbs_per_tx` (not raw `ul_nof_prbs`, see trap 3) and compare the residual
  `last_phr_db + 10·log₁₀(M_RB)`, which isolates the link-budget term
  `P_CMAX − P_O − α·PL`. Round 3 residuals: **A +1.59, B +4.05, C −5.66 dB** —
  only Location C is genuinely power-limited once allocation is removed.
- **Open, do not paper over:** the original ~33 dB deficit's cause is still
  unconfirmed, and the +22 dB July→August jump at 10 m has no mechanism.

### §4 Reliability — RLFs, re-attaches, the Location B obstruction

- **Compare:** event counts per round.
- **Read:** `data_v2/events_by_unit.csv` (`rlf`, `reest`, `release`, `rach`,
  `warnings`, `errors`) · full lines with timestamps in
  `extracted/<unit>/events.csv.gz`.
- **Caveat:** the metal-stand explanation is correlational — removal coincided
  with the churn disappearing. State it as plausible, not established.

### §5 TCP/uplink coupling — why the downlink didn't benefit

- **Compare:** uplink BLER against TCP downlink throughput at the same distance,
  with the UDP downlink at the same distance/config as the control.
- **Read:** `data_v2/phy_by_unit.csv` (`channel=PUSCH`, `bler_first_tx`) joined
  to `throughput_summary.csv` on location/round.
- **The argument:** the downlink radio can sustain far more than TCP achieves —
  proven by UDP DL at the same distance — so the limit is lost TCP ACKs on a
  broken uplink, not downlink capacity.
- **Coda:** fixing the uplink in R3 also lifted 2 m TCP downlink (R2 16.53 →
  R3 22.43 Mb/s).

### §6 Unloaded latency

- **Read:** `data_v2/ping_summary.csv`, `ping_series.csv` (raw captures restored
  to `testing_data/pings/`, so this is reproducible again).
- **Verified:** floor **16.0 / 15.9 / 15.7 ms** at A/B/C, mean 25.0 / 28.1 /
  26.2 ms, 0 % loss, n=30 each. Distance-independent, as expected.
- **Caveat:** Round 3 only, and **there is no 4G ping baseline** — say so.
- The sawtooth (`jitter_mean_abs_delta` 2.48 / 8.66 / 5.35 ms) supports the
  "≈16 ms fixed + wait for uplink grant" decomposition, but the ≈19 ms grant
  period is inferred from the beat, not read from config.

### §7 Bufferbloat

- **Compare:** idle RTT (§6) against RTT under load.
- **Read:** server JSON via `pipeline.iperf.parse_server_json` (`max_rtt_us`
  per stream) · queue depth from `dl_bs_bytes` in `metrics_ue.csv.gz`.
- **State clearly:** diagnosed, not fixed — the RLC resize never happened. Frame
  as a concrete future-work item. It reframes every downlink number in §1
  ("10 Mb/s" vs "10 Mb/s at 2.7 s RTT").

### §8 Control-plane latency

- **Read:** `data/control_plane.csv` (**not yet ported** — see gaps below).
- Round 1 only; say it was not re-measured.

### §9 Software RAN real-time headroom

Two *different* measurements — do not conflate them:

- **PHY decode time per transmission:** `data_v2/phy_by_unit.csv`,
  `proc_us_p50/p99/max`. Across the 12 Round-1 5G tests, PUSCH p99 runs
  **238.9–561.2 µs against a 500 µs slot budget**, exceeding it in 2 of 12; the
  worst single decode is 697.8 µs, i.e. **1.40× over** — which is exactly the
  "up to 1.4× over" already claimed. 4G PUSCH p99 is ~186 µs against a 1 ms
  budget and never approaches it.
- **MAC slot wall-clock latency (new, from `MAC cell`):**
  `data_v2/realtime.csv`. Steady-state avg 19.7–24.6 µs, i.e. comfortably inside
  budget; the per-log maxima of 2.6–3.3 ms are single startup outliers
  (one report per log, ~0.2 %), not a steady-state problem.
- **Caveat:** different host machines for 4G and 5G. State both specs; do not
  sell it as a clean CPU comparison.

### §10 Operational cost of logging — **now across all 31 runs**

- **Read:** `data_v2/logging_cost.csv`.
- **Verified:** 0.41–4.29 MB/s, i.e. **1.4–21.5 GB/hour**, median 5.7 GB/h.
  `metrics_line_share` shows the useful fraction: 0.02–0.08 %.
- Previously computed for Round 1 only; the range is wider than the single
  ~7.5 GB/h figure currently quoted.
- **Recommendation to state:** `warning` level and `hex_max_size 0` for normal
  operation.

### §11 Smaller findings

- **256QAM usage:** `phy_by_unit.csv`, `share_256QAM` for the mix per run;
  `extracted/<unit>/mod_series.csv.gz` for the **ladder over time** (per-second
  modulation counts plus `mean_bits_per_symbol`, straight from the PHY `mod=`
  field — no MCS-table lookup needed, and comparable across the two stacks).
  Do **not** plot mean `dl_mcs`/`ul_mcs` for this: they average an integer index
  and erase the stepping.
  - Verified: 4G at 2 m reaches 256QAM on **39.1 %** of PDSCH — the "39 %"
    already claimed. 5G at 2 m: `UDP_DL` 86.7 %, `TCP_UL` 86.0 %, `UDP_UL`
    95.9 %, consistent with the "86–96 %" claim.
  - **Worth a sentence in §5, not just §11:** at the same distance and config,
    5G TCP DL sits at **9.0 %** 256QAM against UDP DL's **86.7 %**. The ladder
    itself shows the downlink being held back on TCP — an independent line of
    evidence for the uplink-ACK bottleneck, separate from the BLER argument.
    The per-second series shows the mechanism: both start at 256QAM and TCP
    steps down to 64QAM within ~2 s of sustained load and stays there.
- **No incremental redundancy on 5G UL HARQ:** `rv0_share` = **1.0000 across all
  19 5G units** — not approximately, exactly. The sharper version is the
  contrast: **4G** PUSCH `rv0_share` averages 0.9973 (min 0.9833), so srsenb does
  send redundancy versions other than 0, if rarely, and the 5G stack never does.
  That cross-stack comparison was not previously available.
- **Downlink PRB saturation:** `prb_p50`/`prb_max` (5G 51/51, 4G 50/50).

---

## Gaps, honestly

| Gap | Status |
|---|---|
| `control_plane.py` not ported to the new pipeline | §8 still reads the old `data/control_plane.csv`; port before relying on it |
| Figures not regenerated | `figures/*.pdf` are from the old scripts; matplotlib is not installed in this environment |
| MAC pcaps unexploited | 77 MB–1.1 GB each; nothing in §1–§11 needs them |
| NGAP pcaps | Small and rich — full N2 sequence plus AMF identity (`AMFName: open5gs-amf0`, served GUAMI, relative capacity) and an `NGReset` teardown. Good appendix material on the core start-up sequence; **note it is the gNB↔AMF association only**, not the SBI/NRF registration between core NFs, which would need a capture on the core host (`testing_data/logs/` has `amf.log` etc. for that side) |
| No 4G repeats | n=1, by circumstance not design — already explained in the Implementation chapter |

## Two data traps that survive into the new tables

1. **`receiver_Mbps` is 0.00 on the stalled 03-Aug 10 m uplink reps.** Handled:
   `throughput_Mbps` falls back to the interval series and `throughput_src`
   records that it did; `receiver_stalled` flags the rows.
2. **UDP downlink `loss_pct` is meaningless** — `-b 100M -P 8` offers 800 Mb/s
   into a ~40 Mb/s link. `loss_is_meaningful` is 1 only for uplink.
3. **`ul_nof_prbs` / `dl_nof_prbs` are cumulative over the 1 s reporting period,
   not the instantaneous grant.** Values run to tens of thousands in a cell that
   only has 51 PRBs. To get the per-transmission allocation — which is what the
   PHR formula's `10·log₁₀(M_RB)` term needs — divide by the transmission count:

   ```
   M_RB = ul_nof_prbs / (ul_nof_ok + ul_nof_nok)
   ```

   `reps.csv` carries this as `ul_prbs_per_tx` / `dl_prbs_per_tx`. Sanity check:
   the derived value tops out at exactly 51, the cell width. Comparing raw
   `ul_nof_prbs` across runs compares *how much traffic there was*, not how wide
   the grants were.
