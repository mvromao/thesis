# The 2026-08-02 re-run campaign — what the data says

Analysis of `Thesis/testing_data/5G_new_methodology/` — 39 iperf3 reps across 3 locations,
plus 1.87 GB of gNB logs carrying the new `[METRICS ]` reports.

Companion to `FINDINGS.md` (original 24-run campaign) and `SESSION_LOG_2026-08-02.md`
(what was decided in the lab). Reproducible from `analysis/scripts/parse_new_iperf.py`,
`parse_new_metrics.py`, `analyse_new.py`, `test_ovl_hypothesis.py`, `figures_new.py`.

---

## 0. Two things the session log says that the captured data contradicts

Both matter before any result is read.

### 0.1 `rx_gain` was **not** changed to 60 — all three locations ran at 70

`SESSION_LOG_2026-08-02.md` §2 records "**Locked in: `rx_gain: 60`**". The gNB startup
config dump in every one of the three captured logs says otherwise:

| Log | `tx_gain` | `rx_gain` | TDD pattern |
|---|---|---|---|
| `Loc1_2m/gnb.log` (15:13:03) | 89.75 | **70** | 2 DL + 5 sym / 2 UL + 5 sym |
| `Loc2_5m/gnb.log` (15:32:10) | 89.75 | **70** | same |
| `Loc3_10m/gnb.log` (15:49:58) | 89.75 | **70** | same |

Each log contains exactly one startup dump, so the sweep to 60 must have happened on a gNB
instance that was restarted back to 70 before the campaign began. **The receiver-overload
fix was never applied to any measured run.** §3 below shows this is the dominant remaining
problem, so this is the single most important thing to correct.

The TDD rebalance, by contrast, *was* applied exactly as recorded.

### 0.2 The traffic profile changed, so the two campaigns are not directly comparable

Every rep this time ran `iperf3 … -t 20 -i 1 -P 8` — **8 parallel streams** (and `-b 100M`
per stream for UDP, i.e. 800 Mb/s offered). The original campaign was a single stream.
Eight parallel TCP flows recover from loss far better than one, so part of any TCP change
between campaigns is the traffic profile, not the radio. State this in the methodology.

The UDP `loss %` figures (83–89 % on downlink) are an artefact of offering 800 Mb/s into a
~40 Mb/s link and carry no information about link quality — report the *delivered* rate
instead.

---

## 1. Headline: the uplink is fixed, and the downlink paid for it

Mean receiver-side throughput, 3–4 reps per condition (`fig7_tdd_rebalance.pdf`):

| Location | Dir | Proto | 4G baseline | 5G before | 5G after | after ÷ before |
|---|---|---|---|---|---|---|
| 2 m LOS | UL | TCP | 13.1 | 5.1 | **12.6** | 2.5× |
| | UL | UDP | 17.2 | 4.6 | **15.3** | 3.3× |
| 10 m concrete | UL | TCP | 12.6 | 0.58 | **11.6** | **20×** |
| | UL | UDP | 14.1 | 0.54 | **14.2** | **26×** |
| 2 m LOS | DL | TCP | 26.1 | 29.6 | 16.5 | 0.56× |
| | DL | UDP | 21.8 | 46.3 | 36.3 | 0.79× |
| 10 m concrete | DL | TCP | 10.0 | 10.3 | 4.6 | 0.45× |
| | DL | UDP | 10.5 | 27.7 | 19.0 | 0.68× |

*(Mb/s. 5 m omitted — see §2.)*

**The 5G uplink now matches the 4G baseline** at both usable locations: 12.6 vs 13.1 Mb/s at
2 m, 11.6 vs 12.6 Mb/s at 10 m. The pathology documented in `FINDINGS.md` §1–4 is gone.

**The downlink is now below 4G on TCP everywhere** (0.63× at 2 m, 0.46× at 10 m). That is
the cost of the trade, and it is quantitatively exactly what was paid for:

### The downlink loss is fully explained by airtime; the uplink gain is not

The TDD pattern moved DL airtime 68.6 % → 47.1 % (×0.69) and UL airtime 22.9 % → 47.1 %
(×2.06). Scaling the old numbers by those factors and comparing to what was measured:

| Direction | measured ÷ airtime-predicted |
|---|---|
| **DL, 2 m and 10 m** | 0.81, 0.65 (TCP) · **1.14, 0.99** (UDP) |
| **UL, 2 m** | 1.20 (TCP) · 1.60 (UDP) |
| **UL, 10 m** | **9.6× (TCP) · 12.7× (UDP)** |

Downlink UDP lands within 1 % of prediction at 10 m and 14 % at 2 m — **the downlink
regression is purely the airtime you gave away, nothing more**. This is a clean, defensible
result for the thesis: a textbook TDD capacity trade, measured.

The uplink at 2 m is also roughly in line (1.2–1.6× prediction).

**The uplink at 10 m is 10× better than the TDD change alone can explain, and that needs a
caveat rather than a claim** — see §4.

---

## 2. The 5 m data is unusable — the UE re-attached 18 times

`Loc2_5m` is not a valid measurement point:

| Location | PRACH attempts | distinct C-RNTIs | RLF-triggered releases |
|---|---|---|---|
| Loc1_2m | 1 | 1 | **0** |
| **Loc2_5m** | **18** | **18** (0x4601–0x4612) | **9** |
| Loc3_10m | 1 | 1 | **0** |

```
[DU-MNG] ue=0 rnti=0x460f: RLF detected with cause "MAC max consecutive CRC KOs reached".
```

The UE re-attached 18 times in a ~10-minute session, nine of those following a declared
radio link failure.
One rep (`TCP UL rep4`) returned 0.00 Mb/s outright. Rep-to-rep spread at this location is
8.65–22.9 Mb/s on TCP DL and 0–5.9 Mb/s on TCP UL, versus ±0.4 Mb/s at the other two
locations.

Note the RLF *cause* has changed from the original campaign: it was
`max consecutive HARQ NACKs/DTX` (missing uplink feedback), it is now
`max consecutive CRC KOs` (uplink data failing to decode). Both are uplink-rooted.

**Exclude Loc 2 from every table and re-measure it.** Three clean reps at 5 m is the single
highest-value thing to collect if there is another lab session.

---

## 3. The remaining problem: link adaptation over-reaches near the radio

This is the strongest new finding, and it points straight at the `rx_gain` that never got
changed (`fig8_overload_evidence.pdf`). Uplink tests, steady state:

| Location | uplink grants/s | reported PUSCH SINR | chosen MCS | **actual BLER** | PHR |
|---|---|---|---|---|---|
| 2 m LOS | 800 (619 ok / 181 failed) | 20.5 dB | 18.5 | **22 %** | −2.0 dB |
| 5 m partition | 761 (369 / 391) | 14.2 dB | 17.0 | **53 %** | −13.2 dB |
| 10 m concrete | 800 (787 / 13) | 18.0 dB | 12.1 | **1.3 %** | −16.2 dB |

Three observations that only fit together one way:

1. **The scheduler grants the full 800 uplink slots/s the new TDD pattern allows, at every
   location.** (2 UL slots per 2.5 ms period = 800/s — the measured 800 confirms the pattern
   is doing exactly what was intended.) What differs is how many of them decode.
2. **The gNB reports 18–20 dB SINR at both 2 m and 10 m — yet 22 % BLER at 2 m and 1.3 % at
   10 m.** Within each location, BLER falls as SINR rises (correlation −0.26 to −0.74, as it
   should). Across locations the relationship inverts.
3. The difference is the **MCS the link adaptation picks**: 18.5 near the radio, 12.1 far
   from it. At 10 m it picks a conservative MCS against an honest SINR estimate and gets
   1.3 % BLER. Near the radio it picks MCS 18 against a SINR estimate that is roughly 6–10 dB
   optimistic, and one uplink block in five fails.

The mechanism that produces an inflated SINR estimate specifically at high receive levels is
front-end compression: distortion products are not counted as noise by the estimator, so
measured SINR stays high while the constellation is actually damaged. Supporting evidence:

- `pusch_rsrp_db=ovl` (srsRAN's explicit receiver-overload marker) fires **7.2 % of reports
  at Loc 1, 1.9 % at Loc 2, and never at Loc 3** — exactly ordered by received power.
- The lab gain sweep independently found heavy OVL at `rx_gain 70`, clean at `rx_gain 60`.

**Caveat, and it matters:** the `ovl` flag does *not* fire inside the uplink-test windows
themselves (only during downlink tests), so hard ADC saturation during the uplink runs is
not directly demonstrated. The case rests on the SINR/BLER inversion plus the ordering of
the overload flags. Phrase it in the thesis as strongly-supported inference, not proof.

**Concrete action:** re-run Loc 1 at `rx_gain 60` and compare uplink BLER. If it drops from
22 % toward the 1.3 % seen at Loc 3, the diagnosis is confirmed and the 2 m uplink should
rise well above 12.6 Mb/s.

---

## 4. The 10 m result improved more than any logged change can explain

Uplink SINR at the gNB, same nominal locations, same `tx_gain`/`rx_gain`, only the TDD
pattern differing:

| Location | 5G before | 5G after | change |
|---|---|---|---|
| 2 m | +14.8 dB | +20.5 dB | +5.7 dB |
| 5 m | +9.1 dB | +14.2 dB | +5.2 dB |
| **10 m** | **−4.0 dB** | **+18.0 dB** | **+22 dB** |

Loc 1 and Loc 2 both moved by ~5 dB, which is plausible as a second-order effect of cutting
the downlink transmit duty cycle from 68.6 % to 47.1 % (less self-interference from a
transmitter running at `tx_gain 89.75` into the same front end). **Loc 3 moved by 22 dB**,
and nothing in the two configurations accounts for that.

The honest readings are (a) the physical placement at "10 m" was not identical between the
two campaigns, or (b) the original 10 m measurement was corrupted by something transient.
Either way:

> **Do not write "re-balancing the TDD pattern recovered the uplink by 20×".** The airtime
> change accounts for ~2× of it. The rest is unexplained and probably not a config effect.

If there is another lab session, photograph and measure the UE and antenna placement at each
location so this is not ambiguous again.

---

## 5. Smaller observations

- **Real-time health improved.** The original campaign logged 6 lower-PHY late events, 5 FAPI
  late and 2 modulator-busy errors across 12 runs. This campaign, across three much longer
  continuous sessions: **1** lower-PHY late (a PRACH request at Loc 2), **zero** FAPI late,
  **zero** modulator-busy, and 17 RF underflows + 5 RF "late" (1 at Loc 1, 16 + 5 at Loc 3).
  Cutting the downlink duty cycle from 68.6 % to 47.1 % also cut the PHY's peak workload.
- **The `[METRICS ]` capture works and is much better than the old `trace.log`.** Real ISO
  timestamps, key=value, ~1 report/s, and it carries fields the old table never had
  (`ul_olla`, `pusch_invalid_harqs`, `max_pusch_distance`, `avg_crc_delay`,
  `avg_sr_to_pusch_delay`). `parse_new_metrics.py` now handles it — this closes the open TODO
  in `SESSION_LOG_2026-08-02.md` §3.
- **Downlink CQI dropped between campaigns too** (10 m: 10.6 → 8.7; 2 m: 15.0 → 11.9 on TCP),
  which is further evidence for §4's "the physical setup differed" reading, since CQI is a
  UE-side measurement of the downlink and the downlink power configuration did not change.
- **`test.json` is now parsed** — see §7 and §8 below.

---

## 6. What to do next, in priority order

1. **Re-measure Loc 2 (5 m).** Currently unusable; 3 clean reps would complete the distance series.
2. **Set `rx_gain: 60` and re-run Loc 1 (2 m), uplink only.** Directly tests §3. Cheap — 3 reps, ~2 minutes.
3. **Document/photograph physical placement** at all three locations so §4 cannot recur.
4. **Add a single-stream, unloaded latency measurement** — even 30 s of `ping` per location.
   §8 measures RTT only under a saturating 8-stream load, so the *baseline* one-way latency of
   the testbed is still unknown, and it is the number a reader will expect to see for a 5G
   network.
5. *(Optional, if time)* One uplink-only run with the TDD pattern reverted to 3 DL : 1 UL at
   the current placement, to split the TDD effect from everything else empirically — the
   supplementary run already noted in `SESSION_LOG_2026-08-02.md` §4.
6. *(Desk work, no lab needed)* Re-run one downlink test with a smaller RLC/PDCP queue in the
   gNB config to confirm §8's diagnosis and quantify the latency/throughput trade.

---

## Reproducing

```
analysis/scripts/
  rename_reps.py          Loc2/Loc3 CellularLab exports -> <PROTO>_<DIR><rep>.txt (+ manifest)
  parse_new_iperf.py      39 phone-side exports    -> data/new_iperf_reps.csv, new_iperf_series.csv
  parse_new_metrics.py    [METRICS] lines in gnb.log -> data/new_metrics.csv   (replaces the old
                                                       fixed-width trace.log parser)
  analyse_new.py          joins metrics to reps, old-vs-new -> data/new_steady_metrics.csv
  inspect_new.py          per-rep detail and session drift (stdout)
  test_ovl_hypothesis.py  the SINR/BLER inversion in §3 (stdout)
  parse_server_json.py    raw listing of every server-side test object (stdout)
  analyse_server_json.py  session record -> data/server_tests.csv, server_intervals.csv
  figures_new.py          fig7, fig8
  figures_latency.py      fig9
```

Items 1 and 2 together are perhaps 15 minutes of lab time and would make the results chapter
substantially stronger.

---

## 7. The server-side `test.json`, and how many reps were actually run

### 7.1 The three files are cumulative, not per-location

The iperf3 server *was* restarted at each location, but `iperf3 -s --logfile` **appends**
rather than truncating, and the same log path was reused. So each `test.json` is a running
total of everything up to that point, not a per-location capture:

| File | JSON objects | Contains |
|---|---|---|
| `Loc1_2m/test.json` | 17 | warm-up + Loc 1 |
| `Loc2_5m/test.json` | 32 | warm-up + Loc 1 + Loc 2 |
| `Loc3_10m/test.json` | 45 | **the entire session** |

Objects 1–3 (15:03:46, 15:04:14, 15:04:51 UTC) are three TCP downlink runs with no matching
CellularLab export and no `gnb.log` coverage — they predate the Loc 1 gNB start at 15:13:03,
so they are almost certainly warm-up runs from the `rx_gain` sweep. Exclude them.
Objects 4, 17, 32 and 45 are empty trailing records.

**Use `Loc3_10m/test.json` as the single session record.** `analyse_server_json.py` reads it
and assigns each test to a location by timestamp. Note it is concatenated JSON, not a JSON
array — `json.load()` fails; use `jq -s '.'` or `json.JSONDecoder().raw_decode()`.

Next campaign: give `--logfile` a **distinct path per location** (`--logfile Loc1_2m.json`),
since restarting the server does not clear the file.

### 7.2 Rep counts, resolved

Cross-referencing the server records against the CellularLab exports settles the open
question of how many times each Loc 2 condition was run:

| Location | TCP DL | TCP UL | UDP DL | UDP UL |
|---|---|---|---|---|
| Loc 1 (2 m) | 3 | 3 | 3 | 3 |
| **Loc 2 (5 m)** | **4** | **4 attempted, 3 completed** | **4** | **3** |
| Loc 3 (10 m) | 3 | 3 | 3 | 3 |

The fourth Loc 2 TCP uplink attempt (local 16:37:54, now `TCP_UL4.txt`) has a phone-side log
but **no server-side record at all** — the run never completed a test on the server. It is
the rep that reports 0.00 Mb/s. That is independent confirmation that this rep failed rather
than merely performing badly, and it fits the 18 re-attaches documented in §2.

The Loc 2 and Loc 3 exports have been renamed to Loc 1's `<PROTO>_<DIR><rep>.txt` scheme;
each folder now carries a `rename_manifest.csv` mapping every new name back to its original
CellularLab filename and start time (`scripts/rename_reps.py`).

---

## 8. The finding the JSON unlocks: multi-second bufferbloat on the downlink

This is the most significant result in the re-run and it was invisible in the throughput
numbers. For reverse-mode (downlink) tests the core is the TCP **sender**, so its JSON
carries per-second `rtt`, `snd_cwnd` and `retransmits` (`fig9_bufferbloat.pdf`):

| Location | throughput | mean RTT | min RTT | **max RTT** | retransmits | peak data in flight |
|---|---|---|---|---|---|---|
| 2 m LOS | 19.0 Mb/s | 470 ms | 69 ms | 1.66 s | 799 | 3.7 MB |
| 5 m partition | 22.4 Mb/s | 1.20 s | 60 ms | 4.42 s | 843 | 8.8 MB |
| **10 m concrete** | **9.4 Mb/s** | **2.66 s** | 329 ms | **6.70 s** | **1** | 4.9 MB |

A single 10 m run reads like a textbook bufferbloat demonstration — RTT climbing
monotonically from 401 ms to 6542 ms over 20 seconds, congestion window growing from 0.4 MB
to 4.9 MB, and **zero retransmissions for the entire transfer**. CUBIC never receives a
congestion signal, so it never stops growing.

### The queue is inside the gNB, and the gNB's own metrics prove it

The `dl_bs` field in `[METRICS ] Scheduler UE` is the downlink data the gNB has buffered but
not yet transmitted. During the TCP downlink tests:

| Location | mean `dl_bs` | max `dl_bs` | peak in-flight (server) |
|---|---|---|---|
| 2 m | 1.08 MB | 3.30 MB | 3.7 MB |
| 5 m | 2.79 MB | 6.15 MB | 8.8 MB |
| 10 m | 2.51 MB | 4.66 MB | 4.9 MB |

The gNB's buffer occupancy tracks the sender's congestion window almost one-for-one — at
10 m, 4.66 MB buffered against 4.9 MB in flight. Everything TCP puts on the wire is sitting
in the gNB's downlink RLC/PDCP queue. The scheduler's own pipeline is not the culprit:
`max_pdsch_distance` never exceeds 30 ms.

2.5 MB queued at 9.4 Mb/s is **2.1 seconds of standing queue**, which is exactly the measured
mean RTT.

### Why this matters for the thesis

- It is a **latency result**, and the work had none until now. "10 Mb/s downlink" and
  "10 Mb/s downlink at 2.7 s RTT" are very different claims about a network intended to
  host real applications.
- It reframes §1's downlink numbers: the downlink is not merely slower after the TDD
  rebalance, it is slower *and* deeply queued.
- It is actionable and cheap to test: cap the RLC/PDCP queue in the gNB config, or enable
  AQM/ECN, and re-measure. A note that this was diagnosed and how would strengthen the
  conclusions chapter considerably.
- Two distinct regimes are visible and worth a sentence: at 2 m the buffer overflows, so
  TCP gets loss signals and sawtooths (799 retransmissions, RTT oscillating 100–500 ms); at
  10 m the link is slow enough that the queue simply absorbs everything (1 retransmission,
  RTT growing without bound). Same buffer, opposite symptoms.

### Uplink jitter and loss, from the authoritative receiver

For uplink UDP the core is the receiver, so its jitter and loss figures are the ones to
quote (the phone's own `-b 100M -P 8` sender-side loss figures are meaningless):

| Location | jitter | loss |
|---|---|---|
| 2 m | 7.7 – 14.0 ms | 0 – 1.04 % |
| 5 m | 25.2 – **75.2 ms** | 0 – **4.68 %** |
| 10 m | 14.3 – 14.4 ms | 0.09 – 1.11 % |

Loc 3 is remarkably consistent (14.29 / 14.36 / 14.36 ms across three reps). Loc 2 is again
the outlier, consistent with everything else in §2.
