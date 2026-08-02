# What the 24 test logs actually show

Analysis of `Thesis/testing_data/` — 24 runs (2 technologies × 3 distances × {TCP,UDP} × {DL,UL}),
2.81 GB of srsRAN stack traces plus the console metric traces and MAC/NGAP pcaps.

Everything below is reproducible from `analysis/scripts/` (see the end of this file).

---

## 0. The two testbeds are not the same radio system

This has to be stated before any comparison, because it explains most of what follows.
Both configurations were read directly out of the log headers:

| | 4G | 5G SA |
|---|---|---|
| Software | srsRAN 4G `srsenb` @ `6bcbd9e5b` | srsRAN Project gNB @ `29dc1aede7` (dev) |
| SDR | Nuand bladeRF xA4 (SoapySDR) | USRP B210 (UHD) + Leo Bodnar GPSDO |
| RF front end | **BT-100 LNA on RX, BT-200 amp on TX** | **none** |
| RAN host | separate machine from the 5G RAN | separate machine from the 4G RAN |
| Band | Band 7 **FDD** — DL 2680 MHz / UL 2560 MHz | Band **n78 TDD** — 3410.1 MHz (NR-ARFCN 627340) |
| Bandwidth | 10 MHz (50 PRB) | 20 MHz (51 PRB, 30 kHz SCS) |
| TDD pattern | n/a (FDD) | period 5 slots: 3 DL + 6 DL sym / 1 UL + 2 UL sym |
| SDR gains | — | tx_gain 89.75 (device max), rx_gain 70 |
| **UE power cap** | none | **`pcg_p_nr_fr1: -15`** — see §3 |
| Core | Open5GS EPC (shared machine) | Open5GS 5GC (same machine) |
| Test dates | 2026-07-28 | 2026-07-25 |

The core network is the same machine in both campaigns; everything on the RAN side differs.
The 5G link has **2× the bandwidth**, but **2.5 dB more uplink path loss**
(20·log₁₀(3410/2560)), **~23 % of the airtime for uplink** instead of 100 %, **no external
RX amplification**, and a **configured cap on the handset's transmit power**.
Any "5G vs 4G" claim in the thesis must be framed as *this 5G deployment vs this 4G
deployment*, not as a property of the standards.

### Measurement locations

The three locations vary obstruction as well as distance, so "distance" in every table
below is shorthand for a combined distance-plus-obstruction condition:

| | Distance | Obstruction |
|---|---|---|
| Loc 1 | 2 m | clear line of sight to the radio |
| Loc 2 | 5 m | office partition between UE and radio |
| Loc 3 | ~10 m | **concrete wall** between UE and radio |

Material penetration loss rises with frequency, so Loc 2 and Loc 3 penalise the 3410 MHz
5G link more than the 2560 MHz 4G uplink even before any other factor is considered.

---

## 1. Headline: downlink improved, uplink regressed by up to 21×

Mean throughput over the iperf3 steady-state window (`fig1_throughput.pdf`):

| Distance | TCP DL | UDP DL | TCP UL | UDP UL |
|---|---|---|---|---|
| 2 m | 26.1 → **29.6** (1.14×) | 21.8 → **46.3** (2.13×) | 13.1 → **5.1** (0.39×) | 17.2 → **4.6** (0.27×) |
| 5 m | 23.8 → **32.8** (1.38×) | 22.4 → **50.6** (2.26×) | 16.0 → **4.4** (0.27×) | 15.8 → **0.8** (0.05×) |
| 10 m | 10.0 → **10.3** (1.03×) | 10.5 → **27.7** (2.63×) | 12.6 → **0.6** (0.05×) | 14.1 → **0.5** (0.04×) |

*(4G → 5G, Mb/s; peak observed 5G DL was 60 Mb/s at 2 m UDP)*

Two things jump out and both are worth a section in the results chapter:

1. **5G doubles UDP downlink throughput but barely moves TCP downlink** (1.03–1.38×).
   The 5G radio clearly *can* carry ~50 Mb/s; TCP does not take it.
2. **5G uplink is worse than 4G uplink at every distance**, and collapses to
   ~0.5 Mb/s at 10 m — 21× below 4G at the same distance.

---

## 2. The uplink deficit decomposes exactly into two factors

This is the cleanest quantitative result in the dataset. Counting actual uplink
grants per second from the metric traces:

| | uplink grants/s | bits per grant | throughput |
|---|---|---|---|
| 4G @ 2 m | 976 | 13 429 | 13.1 Mb/s |
| 5G @ 2 m | 372 | 13 634 | 5.1 Mb/s |
| 4G @ 10 m | 971 | 12 931 | 12.6 Mb/s |
| 5G @ 10 m | 394 | 1 485 | 0.6 Mb/s |

- **Factor A — TDD airtime.** The configured pattern gives exactly one uplink slot per
  2.5 ms period → a hard ceiling of **400 uplink transmissions per second**. The measured
  372–394 grants/s confirms it. 4G FDD gets one uplink subframe per millisecond → ~975/s.
  That is a **2.5× structural penalty** that no amount of signal quality can recover.
- **Factor B — link budget.** At 2 m the *payload per grant is identical* between the two
  systems (13 634 vs 13 429 bits). At 10 m the 5G payload has collapsed **8.7×** while 4G's
  is unchanged.

Multiply them: 2.5 × 1.0 = 2.6× deficit at 2 m (measured 2.59×), and 2.5 × 8.7 = 21.5×
at 10 m (measured 21.5×). The decomposition is exact.

**Thesis takeaway:** at short range the 5G uplink shortfall is *purely a TDD configuration
choice* and is recoverable by re-balancing `tdd_ul_dl_cfg`. At 10 m a second problem
dominates — and §3 shows that one is also a configuration effect, not a physical limit.

The 3 DL : 1 UL pattern was not chosen for this experiment; it came from a worked example
adopted to resolve an earlier problem and was never revisited. That makes it a clean thing
to change and re-measure.

---

## 3. That second problem: the 5G uplink falls apart with distance, the 4G one does not

Uplink SINR at the base station, averaged over the active window of the console metric
traces (the ~290 k individual PUSCH records extracted from the stack traces show the same
trend and are what `fig5_ul_sinr.pdf` plots):

| Distance | 4G mean SINR | 5G mean SINR | 4G UL modulation | 5G UL modulation |
|---|---|---|---|---|
| 2 m | +13.7 dB | +10.7 dB | 99 % 16QAM | mixed QPSK…256QAM |
| 5 m | +14.2 dB | +7.1 dB | 99 % 16QAM | mixed |
| 10 m | +11.5 dB | **−7.6 dB** | 99 % 16QAM | **99.9 % QPSK, MCS 0** |

4G's uplink is essentially **flat across the whole 2–10 m range** (11.5–14.2 dB, σ ≈ 1–4 dB)
even though free-space loss over 2 m → 10 m is 14 dB. 5G loses **18 dB** over the same
8 metres and its variance explodes (σ up to 14 dB).

**The power headroom report explains the difference, and it is the single most diagnostic
number in the dataset.** Closed-loop uplink power control is supposed to hold received SINR
constant by making the UE transmit harder as it moves away — which is exactly what the flat
4G curve is:

| Location | 4G PHR | 5G PHR |
|---|---|---|
| 2 m, LOS | **+20.0 dB** | **−2.0 dB** |
| 5 m, partition | **+16.6 dB** | **−10.3 dB** |
| 10 m, concrete wall | **+12.3 dB** | **−13.6 dB** |

In 4G the handset has 12–20 dB of transmit power in reserve everywhere, so power control
absorbs the path loss and SINR stays put. In 5G the PHR is **negative at 2 metres in clear
line of sight** — the UE is already power-limited at the easiest test point and has nothing
left to give. Every extra decibel of loss then lands directly on the received SINR.

### The cause is a configured transmit-power cap on the handset

`files/gnb.yaml` line 46 contains:

```yaml
pcg_p_nr_fr1: -15    # Forces the phone to drop its tx power by 25 dB
```

`p-NR-FR1` (TS 38.331 `PhysicalCellGroupConfig`) caps the UE's **total configured maximum
output power for FR1**. Setting it to −15 dBm reduces the handset's ceiling from the normal
+23 dBm (power class 3) to −15 dBm — a **38 dB reduction**, applied at every location.

The measured PHR confirms it independently. Inverting the TS 38.213 §7.7.1 Type-1 PHR
equation with the values actually read out of the logs (`p0-NominalWithGrant` = −76 dBm from
SIB1, mean PUSCH allocation 42 PRB, 30 kHz SCS, α = 1) gives the implied path loss:

| Location | measured PHR | implied loss if P_CMAX = **+23 dBm** | implied loss if P_CMAX = **−15 dBm** | free-space loss |
|---|---|---|---|---|
| 2 m | −2.03 dB | 81.8 dB (**+32.7 dB excess**) | 43.8 dB (−5.3 dB) | 49.1 dB |
| 5 m | −10.34 dB | 90.1 dB (**+33.0 dB excess**) | 52.1 dB (−5.0 dB) | 57.1 dB |
| 10 m | −13.55 dB | 93.3 dB (**+30.2 dB excess**) | 55.3 dB (−7.8 dB) | 63.1 dB |

Under the uncapped hypothesis the unexplained excess is **a constant ~33 dB at all three
locations**. A constant offset that does not vary with distance or obstruction cannot be
propagation — it is the signature of a fixed transmit-power reduction. Under the capped
hypothesis the implied loss tracks free space to within 5–8 dB, which is exactly what
antenna gain plus the uncalibrated declared `ss-PBCH-BlockPower` (−16 dBm) would produce.

**So the 5G uplink was not broken by the radio environment. It was configured to whisper,
and the SDR gains were then cranked to their limits (tx_gain 89.75 = device maximum,
rx_gain 70, versus 50/45 in the reference config) to compensate.** This is a gain-staging
mistake, and it accounts for essentially all of §2's factor B, §4, §5 and §6.

Secondary contributors, all much smaller and all still worth a sentence:

- **No external RX amplification on the 5G side.** The 4G bladeRF has a BT-100 LNA in front
  of its receiver; the B210 has nothing. This directly degrades uplink noise figure.
- **Frequency-dependent penetration loss** at Loc 2 (partition) and Loc 3 (concrete wall)
  hits 3410 MHz harder than 2560 MHz.
- **Power spectral density**: the UE spreads its (already capped) power over 42 PRB of a
  20 MHz carrier rather than 44 PRB of a 10 MHz one.
- 2.5 dB extra free-space loss at 3410 MHz vs 2560 MHz.

---

## 4. Why 5G TCP downlink does not benefit: the return path is broken

First-transmission PUSCH BLER measured at the base station (`fig3_ul_bler.pdf`):

| Test | uplink BLER | DL throughput |
|---|---|---|
| 5G 10 m **TCP** DL | **53.7 %** (11 826 of 22 004 blocks failed) | 10.3 Mb/s |
| 5G 10 m **UDP** DL | 3.7 % | 27.7 Mb/s |
| 4G 10 m TCP DL | 0.25 % | 10.0 Mb/s |

In the 5G TCP downlink test the uplink is carrying a continuous TCP ACK stream — and
**loses more than half of it**. The UDP test at the identical distance has almost no uplink
traffic and shows 3.7 %. The mechanism chain is visible end to end in the logs:

1. Poor uplink SINR → link adaptation stuck at MCS 0 / QPSK
2. → 53.7 % PUSCH first-transmission failures
3. → TCP ACKs lost → sender's congestion window never opens
4. → downlink throughput stalls at 10 Mb/s while the radio can do 27.7

There is a second-order consequence worth flagging: the **DL BLER reported in the metric
trace (46 % for this test) is not downlink decoding failure** — it is missing uplink HARQ
feedback being counted as NACK/DTX. The 5G 10 m UDP DL run at the same distance reports
only 5.5 %. Same downlink, same distance, different uplink load.

**Thesis takeaway:** in a TDD system with a weak uplink, uplink quality bounds *downlink*
TCP performance. That is a more interesting result than a throughput table.

---

## 5. False radio link failures at 2 metres

`5G/Loc_1_2m/UDP/DL` contains **7 UEContextReleases and repeated**:

```
[MAC ] ue=0: RLF detected. Cause: 100 consecutive HARQ-ACK KOs
[DU-MNG] ue=0 rnti=0x4603: RLF detected with cause "MAC max consecutive HARQ NACKs/DTX
         reached". Timer of 4000 msec to release UE started...
```

At **2 metres**, during a saturated downlink flood. The UE then re-attaches, gets a new
RNTI, and the cycle repeats — the log shows the UE churning through rnti 0x4601 → 0x4604.
This is not coverage; it is the gNB never receiving the HARQ-ACKs on PUCCH/PUSCH, i.e. the
same uplink weakness as §3–4. **9 RLFs across the 5G campaign, 0 across the 4G campaign.**

The same file shows an NGAP race worth a footnote: the AMF issues a
`PDUSessionResourceSetupRequest` 0.3 ms after a `UEContextReleaseCommand` for the same UE,
and the gNB answers with `ErrorIndication` — an Open5GS/srsRAN interop rough edge during
rapid re-attach.

---

## 6. Uplink HARQ uses no incremental redundancy

Across **all 12 five-G runs, 100 % of PUSCH transmissions carry `rv=0`** — including the
retransmissions. Retransmissions definitely happen (tracking HARQ process ids in
`5G/Loc_3_10m/TCP/DL`: only 60.5 % of transport blocks decode on the first attempt, 6.3 %
need six attempts, 1.1 % need eleven), but every one repeats redundancy version 0.

srsRAN 4G by contrast cycles rv 0→2→3→1 normally (rv≠0 present in most runs).

So the 5G uplink is getting **Chase combining only, no coding gain from incremental
redundancy** — exactly where a 53 % BLER link needs it most. Setting `rv_sequence` in
the gNB config is a concrete, cheap improvement to propose in the conclusions.

---

## 7. The software base station runs at the edge of its real-time deadline

srsRAN logs the CPU time it spent on every transmission. Against the 5G slot budget of
**500 µs** at 30 kHz SCS (`fig4_processing_time.pdf`):

| | mean | p95 | p99 | max |
|---|---|---|---|---|
| 5G PUSCH decode | ~200 µs | **420–440 µs** | **460–560 µs** | **~700 µs** |
| 4G PUSCH decode | ~195 µs | ~250 µs | ~300 µs | ~640 µs (budget 1000 µs) |

The 5G p99 **exceeds the slot deadline** in several runs and the worst case is 1.4× over.
That is not a theoretical concern — the logs contain the consequences:

```
[PHY ] Real-time failure in lower PHY: Downlink data late for sector 0 and slot 44.0
[FAPI] Real-time failure in FAPI: Received late DL_TTI.request from slot 44.7
[PHY ] The modulator is busy.
[RF  ] Real-time failure in RF: underflow
[SCHED] Discarding error indication. Cause: Scheduler results ... already been erased
```

**5G: 6 lower-PHY late events, 5 FAPI late events, 2 modulator-busy errors, 6 RF underflows.
4G: none of any kind.** 4G gets a 1 ms budget on half the bandwidth and never comes close.

This is a genuinely useful result for a thesis about *keeping* a network running in a lab:
it quantifies how much headroom the host has left, and it says the 20 MHz n78 configuration
on this hardware is at the limit, not comfortably inside it.

**Caveat:** the two RANs ran on different host machines, so this is not a like-for-like CPU
comparison. The absolute 5G figures against the 500 µs deadline stand on their own — those
are measured on the machine that actually ran the gNB — but the "4G never comes close"
contrast also reflects a 1 ms budget on half the bandwidth, and possibly a different CPU.
State both host specifications in the results chapter.

---

## 8. Control plane: 5G SA attach is ~2.2× slower than 4G

Single-attempt attaches only (`fig6_control_plane.pdf`):

| Stage | 4G | 5G SA |
|---|---|---|
| NG/S1 setup (gNB↔core) | **1.9 ms** | **9.5 ms** |
| RRC connection setup | 34 ms | 32 ms |
| AS security mode | 38 ms | 24 ms |
| Initial context setup | 109 ms | 72 ms |
| PDU session / E-RAB setup | (in ICS) 109 ms | 52 ms |
| **RRC request → usable bearer** | **166 ms** | **360 ms** |

The air-interface stages are comparable or *faster* in 5G. The extra ~200 ms comes from
the 5G procedure being split into more steps (registration, then a separate
`PDUSessionResourceSetup`) plus the extra NAS round trips to the AMF/AUSF/UDM and the
CU-CP/CU-UP/DU internal E1/F1 exchanges — all visible in the trace. The **5× slower NG
setup** (9.5 ms vs 1.9 ms) is the SBI-based core showing up directly.

Only one run captured a *complete initial registration* (the others are Service Requests
from an already-registered UE, identifiable by the ~2 ms instead of ~178 ms NAS phase):
`5G/Loc_1_2m/TCP/DL`, `InitialUEMessage` 10:25:09.452 → `PDUSessionResourceSetupResponse`
10:25:09.919 = **467 ms**, of which 178 ms is authentication against the AMF/AUSF/UDM.

---

## 9. Operational: logging cost of a permanently-running network

The 24 runs produced **2.81 GB of stack traces over 1341 s** of capture at `info` level with
`hex_max_size: 64`.

- Average **2.1 MB/s**; peak **6.0 MB/s** (82 000 log lines/s) during a saturated downlink test.
- **57–77 % of every log file is hex payload dumps.**
- Extrapolated to continuous operation: **~7.5 GB/hour, ~180 GB/day.**

For a lab network that is meant to stay up, this is a real constraint and a concrete
recommendation: run at `warning` level with `hex_max_size: 0` for normal operation and
raise it only for measurement campaigns.

Also worth a line: **`enb_metrics.csv` is empty (`#eof`) in all 12 4G runs** — the CSV metrics
exporter produced nothing, so every 4G KPI here had to be recovered from the console trace.
If more campaigns are planned, fix that first.

---

## 10. Smaller things worth a sentence each

- **256QAM is actually being used.** 5G PDSCH runs 86–96 % 256QAM at 2–5 m; 4G PDSCH reaches
  256QAM 39 % of the time at 2 m. Both stacks are exercising the full modulation ladder.
- **Downlink PRB occupancy is saturated** in both systems (4G 49.6/50, 5G 47–49/51), so the
  downlink is throughput-limited by modulation and BLER, not by scheduling.
- **4G carrier frequency offset** stays within ±1 kHz (σ 6–78 Hz) at 2.56 GHz — 0.4 ppm,
  i.e. the bladeRF's oscillator is not a limiting factor.
- **The 4G eNB emits 4 `RF Overflow` messages at every startup** and none thereafter — a
  benign SoapySDR/bladeRF stream-priming artefact, worth knowing so it is not mistaken for
  a fault.
- **TCP vs UDP in 4G is a non-event** (ratios 0.84–1.31); in 5G downlink UDP beats TCP by
  1.54–2.70×. The protocol sensitivity is specific to the 5G configuration, which reinforces §4.

---

## Suggested structure for the results chapter

1. Testbed asymmetry table (§0) — establishes honesty up front
2. Throughput results (§1) with `fig1`, `fig2`
3. Uplink decomposition (§2) — the strongest quantitative result
4. Radio-quality analysis (§3) with `fig5`
5. TCP/uplink coupling (§4) with `fig3` — the most interesting finding
6. Stability: RLF and connection churn (§5)
7. Control-plane latency (§8) with `fig6`
8. Feasibility of a software RAN on commodity hardware (§7) with `fig4`
9. Operational lessons (§9) — fits the "keep it running in the lab" objective

## Re-run plan

The existing campaign is **not wasted** — keep every result. The contrast between the
mis-staged configuration and a corrected one is itself a thesis contribution: *"the effect
of UE transmit-power configuration and TDD pattern on uplink performance in an SDR
testbed"* is a better section than another throughput table. Present the current data as
the "as-deployed" condition and the re-run as the "corrected" condition.

Priority order, assuming one lab session of roughly two hours.

### Step 0 — gain staging at Loc 1 (~25 min). Do this first; nothing else is valid without it.

The single change that matters: **remove `pcg_p_nr_fr1: -15`** (or set it to `23`) so the
handset can use its full power class 3 output.

That cap was almost certainly added to stop the receiver being overloaded by a UE at 2 m.
Removing it while leaving `rx_gain: 70` and `tx_gain: 89.75` will simply move the problem
to ADC clipping. Fix the whole gain chain at once:

1. Remove the power cap.
2. Return `tx_gain` and `rx_gain` towards the reference values (50 / 45) as a starting point.
3. At Loc 1, run a 20 s uplink iperf3 and step `rx_gain` over ~35 / 45 / 55 / 65, recording
   mean PUSCH SINR, uplink MCS and BLER from the console trace at each setting.
4. Pick the `rx_gain` that maximises SINR. **The success criterion is that PHR becomes
   positive** — that means the UE is no longer power-limited and closed-loop power control
   has room to work, which is the whole point.

Record this sweep; it is a figure in its own right and it documents a calibration step that
the original campaign never performed.

### Step 1 — full campaign with the corrected configuration (~45 min)

3 locations × {TCP, UDP} × {DL, UL} = 12 runs. **Run each cell three times**, not once —
the current dataset has n = 1 everywhere and therefore carries no error bars. Three 20 s
runs cost less time than one 60 s run and give a usable spread.

### Step 2 — TDD pattern variant (~25 min)

Change to a balanced pattern (`nof_dl_slots: 2, nof_ul_slots: 2`) and repeat **uplink only**
at all three locations. This isolates factor A from factor B in §2 and turns the
decomposition into a controlled experiment rather than an inference. Predicted effect:
uplink grants rise from ~390/s to ~780/s and uplink throughput roughly doubles at Loc 1.

### Step 3 — only if time remains

- `nof_antennas_ul: 2`. The B210 has a second receive channel that is currently unused;
  two RX antennas give roughly 3 dB of combining gain on the uplink for the cost of one
  extra antenna. Re-run uplink at Loc 3 (the hardest point).
- Borrow the **BT-100 LNA** from the 4G rig for the B210 receive path, if its datasheet
  covers 3.4 GHz. This removes the front-end asymmetry noted in §0 and §3.
- Enable **SRS** — the log shows `SRS (n/a)`, so uplink link adaptation is running on PUSCH
  DMRS only, with no wideband sounding.

### Collect these regardless of how far you get

- **`iperf3 --json`** on the client. Retransmission counts, RTT and UDP loss/jitter would
  turn §4 from a well-supported inference into a direct measurement. This is the single
  highest-value addition and costs nothing.
- Log at `all_level: warning` with `hex_max_size: 0` (see §9) — 3.9 GB for 24 runs is
  unnecessary, and the console metric trace carries almost every KPI used in this analysis.
- Note the **host machine specification for the gNB** so §7 can be stated cleanly.
- Leave the 4G side completely untouched so the existing baseline stays valid.

### Do not change

Band, bandwidth, SCS and SDR should stay as they are. They are part of what the thesis is
characterising, and changing them would invalidate comparison with the existing data.

---

## Reproducing

```
analysis/scripts/
  parse_traces.py     24 console metric traces  -> data/trace_tidy.csv   (922 samples)
  analyse.py          steady-state KPI tables   -> data/summary_kpis.csv
  scan_events.py      streaming pass over 2.8 GB -> data/events.json      (log levels, W/E templates)
  report_events.py    event tables              -> data/event_summary.csv
  scan_phy.py         per-transmission PHY      -> data/phy.json          (~700 k transmissions)
  report_phy.py       PHY tables                -> data/phy_summary.csv
  control_plane.py    attach/registration timing-> data/control_plane.csv
  harq_check.py       HARQ retransmission audit (prints to stdout)
  figures.py          all six figures           -> figures/*.pdf,*.png
```

Requires `pandas`, `numpy`, `matplotlib`. Run from any directory; paths are absolute
inside the scripts and point at `Thesis/testing_data/`.
