# Column reference

One line per column. Units are in the column name wherever they exist
(`_bps`, `_Mbps`, `_db`, `_ms`, `_us`, `_ns`, `_s`, `_bytes`).
`_share` and `_rate` columns are fractions in 0–1, not percentages.

---

## Identity columns (appear in most tables)

| Column | Meaning |
|---|---|
| `rep_id` | Unique id of one iperf3 repetition, e.g. `R3_5G_A_TCP_UL_r2`. |
| `unit_id` | Unique id of one stack log = one streaming pass, e.g. `R2_5G_A`. |
| `round` | Test round 1, 2 or 3. |
| `campaign` | Calendar date(s) the round was run. |
| `tech` | `4G` or `5G`. |
| `location` | Test location A, B or C. |
| `distance_m` | Tape-measured distance from the radio: A=2, B=6, C=10. |
| `protocol` | `TCP` or `UDP`. |
| `direction` | `DL` (UE downloading) or `UL` (UE uploading). |
| `rep` | Repetition number within that condition (1–4). |
| `variant` | Blank normally; `TDD31` for the Round 3 TDD isolation run. |
| `rx_gain` / `tx_gain` | SDR receive / transmit gain, read from the log's own config dump. Blank for 4G — srsenb prints no configuration. |
| `tdd` | TDD slot pattern, e.g. `2DL:2UL`. `n/a` for 4G, which is FDD. |

---

## `reps.csv` — one row per iperf3 repetition (102 rows)

### Throughput

| Column | Meaning |
|---|---|
| `throughput_Mbps` | **The headline figure for this repetition.** Chosen per the rules below. |
| `throughput_src` | Which source `throughput_Mbps` came from — always check this before quoting the number. |
| `sender_Mbps` | Final iperf3 sender-side total. |
| `receiver_Mbps` | Final iperf3 receiver-side total. Authoritative when non-zero. |
| `mean_Mbps_5s_on` | Mean of the per-second `[SUM]` intervals, first 5 s dropped (TCP ramp-up). |
| `min_Mbps` / `max_Mbps` | Min / max per-second interval, after the 5 s ramp. |
| `receiver_stalled` | 1 = the iperf3 results exchange failed and `receiver_Mbps` is a false 0.00; the interval series was used instead. |
| `n_samples` | Number of 1 Hz metric reports (Rounds 2–3) or console rows (Round 1) behind this row's averages. |
| `start_utc` | Repetition start, UTC, taken from the export's `Time:` line (**not** the app's local-time banner). |
| `time_aligned` | 1 = radio metrics were joined by timestamp. 0 = Round 1, sequence-aligned only (its console log carries no timestamps). |

### UDP only

| Column | Meaning |
|---|---|
| `jitter_ms` | Receiver-side packet delay variation. |
| `loss_pct` | Datagrams lost, percent. |
| `loss_is_meaningful` | 1 = uplink, loss reflects the link. 0 = downlink, where `-b 100M -P 8` offers ~800 Mb/s into a ~40 Mb/s link, so "loss" is the generator outrunning the radio. |

### Radio conditions (averaged over the repetition window)

| Column | Meaning |
|---|---|
| `pusch_snr_db` | Uplink signal-to-noise ratio measured at the gNB on the data channel. |
| `pusch_rsrp_db` | Uplink received power at the gNB. |
| `rsrp_ovl_share` | Fraction of reports where RSRP came back `ovl` — the receiver front end was saturated. Non-zero means overload, not missing data. |
| `last_phr_db` | Last reported Power Headroom by the UE to the gNB: spare transmit power. Negative = power-limited. Contains a −10·log₁₀(M_RB) term, so only comparable at equal grant width. |
| `phr_residual_db` | `last_phr_db + 10·log₁₀(M_RB)` — PHR with the grant-width term removed, leaving the link-budget part. **This is the one to compare between locations.** |
| `ul_prbs_per_tx` / `dl_prbs_per_tx` | Mean resource blocks per transmission (grant width). Max possible is 51. |
| `ul_nof_prbs` / `dl_nof_prbs` | **Cumulative** PRBs over each 1 s reporting period, not the grant size — runs to tens of thousands. Divide by the transmission count, or just use `*_prbs_per_tx`. |
| `ul_mcs` / `dl_mcs` | **Mean** of the per-second MCS index over the repetition. MCS is an integer 0–28 as logged, so this is a summary, not a value the radio ever used — averaging hides the adaptation. For a modulation ladder use `mod_series.csv.gz`, not this. An MCS index also does not name a modulation on its own: the mapping depends on the configured MCS table. |
| `ul_error_rate` / `dl_error_rate` | Block error rate, fraction 0–1. |
| `cqi` | Channel Quality Indicator reported by the UE for the downlink, 0–15. |
| `ul_brate_bps` / `dl_brate_bps` | Bit rate as the gNB scheduler measured it (cross-check on the iperf3 figure). |
| `dl_bs_bytes` | Downlink buffer status: bytes queued in the gNB waiting to send. **This is the bufferbloat metric.** |
| `bsr_bytes` | Buffer Status Report: bytes the UE says it has waiting to send. |
| `ta_ns` | Timing advance — propagation delay correction applied to the UE. |
| `avg_sr_to_pusch_delay_ms` | Mean delay from the UE asking to transmit to actually getting a grant — uplink access latency. |

---

## `throughput_summary.csv` — repetitions aggregated (49 rows)

One row per (round × location × protocol × direction × variant). This is the
main comparison table.

| Column | Meaning |
|---|---|
| `n` | Repetitions in this cell. |
| `n_valid` | Of those, how many produced a usable throughput figure. |
| `mean_Mbps` | Mean of `throughput_Mbps` across the repetitions. |
| `sd_Mbps` | Standard deviation. Blank when n=1. A large value flags an unstable cell (e.g. Round 2 Location B). |
| `min_Mbps` / `max_Mbps` | Range across repetitions. |
| `pusch_snr_db`, `last_phr_db`, `ul_mcs`, `ul_error_rate`, `dl_error_rate`, `rsrp_ovl_share` | Means of the same columns in `reps.csv`. |

---

## `phy_by_unit.csv` — per-transmission PHY, one row per log × channel (62 rows)

| Column | Meaning |
|---|---|
| `channel` | `PUSCH` (uplink data) or `PDSCH` (downlink data). |
| `n` | Transmissions observed. |
| `bler_first_tx` | First-transmission block error rate, from `crc=OK/KO`. PUSCH only — the gNB doesn't see downlink CRC results. |
| `rv0_share` | Fraction of transmissions sent at redundancy version 0. **1.0 = no incremental redundancy at all**: every retransmission repeats the original bits rather than sending new parity. |
| `share_256QAM` / `share_64QAM` / `share_QPSK` | Modulation mix. Normalised across both stacks (4G logs bits/symbol, 5G logs names). |
| `sinr_p50` / `sinr_p5` | Median and 5th-percentile SINR per transmission. |
| `prb_p50` / `prb_max` | Median / max allocation width in resource blocks. |
| `proc_us_p50` / `p99` / `max` | Time the software base station took to process one transmission. **Compare against the 500 µs slot budget (5G) or 1 ms subframe (4G)** — this is the real-time headroom result. |

---

## `tdd_airtime.csv` — where uplink actually lands in the TDD pattern (7 rows)

| Column | Meaning |
|---|---|
| `ul_slot_fraction_cfg` | Uplink share of slots as *configured* (0.5 for 2DL:2UL, 0.25 for 3DL:1UL). |
| `pusch_rb_slot0..4` | Mean uplink resource blocks used at each slot position in the TDD period. **The airtime ceiling, measured**: non-zero only in slots 3–4 at 2DL:2UL, only slot 4 at 3DL:1UL. |
| `pdsch_rb_slot0..4` | Same for downlink. |
| `ul_rb_share_measured` | Uplink share of all resource blocks used. Reflects the session's traffic mix as well as the pattern — use the per-slot columns for the airtime argument. |
| `mean_ul_brate_Mbps` / `mean_dl_brate_Mbps` | Cell throughput while busy. |
| `late_ul_harqs` / `late_dl_harqs` | HARQ feedback that arrived too late to use. |
| `n_busy_samples` | 1 Hz cell reports where traffic was actually flowing. |

---

## `realtime.csv` — MAC slot timing vs deadline (7 rows, 5G only)

| Column | Meaning |
|---|---|
| `slot_budget_us` | Hard deadline per slot: 500 µs at 30 kHz subcarrier spacing. |
| `n_reports` | 1 Hz MAC reports in the log. |
| `wall_clock_avg_us` | Mean actual slot processing time. |
| `wall_clock_max_us` | Worst single slot. The multi-millisecond maxima are startup outliers, not steady state. |
| `reports_over_budget` / `share_over_budget` | Reports whose worst slot exceeded the budget. |
| `sched_latency_avg_us` | Time spent in the scheduler alone. |
| `slot_ind_msg_time_diff_avg_us` | Gap between slot indications — should sit at 500 µs; drift means the radio clock and the host are diverging. |
| `involuntary_ctx_switches` | Times the OS pre-empted the RAN thread. Non-zero is a real-time risk on a general-purpose OS. |

---

## `logging_cost.csv` — cost of running with logging on (31 rows)

| Column | Meaning |
|---|---|
| `duration_s` | Wall-clock span of the log. |
| `log_bytes` / `lines_total` | Raw size and line count. |
| `bytes_per_s` / `gb_per_hour` | Logging rate, and that rate extrapolated to continuous operation. |
| `metrics_lines` / `metrics_line_share` | How many lines were `[METRICS ]`, and their fraction of the file (0.0002–0.0008). |
| `hexdump_byte_share` | Fraction of bytes that are hex-dump continuation lines — removable with `hex_max_size 0`. |
| `share_RLC`, `share_PDCP`, `share_PHY`, … | Fraction of bytes from each protocol layer. |

---

## `events_by_unit.csv` — counts per log (31 rows)

| Column | Meaning |
|---|---|
| `warnings` / `errors` | Lines logged at W / E level. |
| `rlf` | Radio link failures. |
| `reest` | RRC re-establishment attempts — the UE lost the connection and tried to recover. |
| `release` | UE context releases. |
| `rach` | Random-access events; a spike means repeated re-attaching. |
| `phy_dl_late` / `phy_ul_late` | Data handed to the radio too late for its slot. |
| `phy_rt_failure` | Lower-PHY real-time failure. |
| `rf_underflow` / `rf_overflow` | SDR sample buffer ran dry / overran — the host couldn't keep up. |
| `harq_maxretx` | Transmissions dropped after exhausting HARQ retries. |
| `sched_err_ind` | Scheduler discarded an error indication. |

---

## `ping_summary.csv` / `ping_series.csv` — unloaded latency (Round 3 only)

| Column | Meaning |
|---|---|
| `n` / `sent` / `recv` / `loss_pct` | Echo counts and loss. |
| `min` | **The latency floor** — the headline number. |
| `mean` / `median` / `max` / `p95` / `sd` | Distribution of round-trip time, ms. |
| `jitter_mean_abs_delta` | Mean absolute change between consecutive RTTs — the sawtooth amplitude. |
| `reported_*` | The min/avg/max/mdev `ping` printed itself, as a cross-check on the computed values. |
| `seq` / `ttl` / `rtt_ms` | (`ping_series`) Per-echo sequence number, TTL, round-trip time. |

---

## `extracted/<unit>/` — the raw 1 Hz extracts

| File | Contents |
|---|---|
| `metrics_ue.csv.gz` | `[METRICS ] Scheduler UE` — per-UE radio KPIs, same column meanings as the radio block of `reps.csv`, plus `ts` (UTC) and `t_rel_s` (seconds from log start). |
| `metrics_cell.csv.gz` | `[METRICS ] Scheduler cell` — cell totals, slot counts, per-slot PRB arrays (pipe-separated), late HARQs, PDCCH/UCI failures. |
| `metrics_mac.csv.gz` | `[METRICS ] MAC cell` — slot timing, all in µs, against `slot_duration_us`. |
| `mod_series.csv.gz` | **The modulation ladder over time.** One row per second per channel: `ts`, `t_rel_s`, `channel` (PUSCH/PDSCH), counts of `QPSK`/`16QAM`/`64QAM`/`256QAM`, `total`, `share_256QAM`, and `mean_bits_per_symbol` (2/4/6/8 weighted — a single number to plot as the ladder). Taken from the PHY `mod=` field, so it states the modulation directly and needs no MCS-table lookup. Works for both 4G and 5G (srsenb logs bits/symbol, normalised here). |
| `events.csv.gz` | Every warning/error line: `ts`, `layer`, `level`, `classes` (pipe-separated event tags), `message`. |
| `census.json` | Line and byte accounting by layer and level; feeds `logging_cost.csv`. |
| `phy_summary.json` | Full percentile distributions behind `phy_by_unit.csv`. |
