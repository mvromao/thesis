# The 2026-08-03 campaign — what the data says

Analysis of `Thesis/testing_data/03-Aug/` — 36 iperf3 reps at `rx_gain: 60` across three
locations, plus a 3-rep TDD isolation run, and 1.9 GB of gNB logs.

Companion to `FINDINGS.md` (July campaign), `FINDINGS_RERUN_2026-08-02.md` (the `rx_gain 70`
re-run) and `SESSION_LOG_2026-08-03.md` (what happened in the lab).
Reproducible from `analysis/scripts/parse_0803_*.py`, `analyse_0803.py`, `figures_0803.py`.

---

## 0. Housekeeping answers to the session log's open questions

| Session-log open item | Answer |
|---|---|
| "24 tests" — verify rep count | **36**, as originally planned: 3 locations × 2 protocols × 2 directions × 3 reps. All present and classifiable. |
| Loc 2 churn — is it fixed? | **Yes, completely.** 1 PRACH, 1 `rrcSetupRequest`, 1 C-RNTI, **0 RLFs** at every location, including the TDD run. The August 18-re-attach pathology is gone. |
| PHR anomaly (−10/−12 today vs −1/0 on 08-02) | **Not an anomaly — resolved.** See §3. |
| TDD isolation result | **Read out below — but it does not answer the question it was designed to answer.** See §4. |
| `PLACEMENT.md` + photos | **Not present** in the copied data. |
| ping files | Present as `03-Aug/ping_Loc1..3` (no file extension, at the campaign root). **30 echoes each, `-c 30`, 0 % loss.** Analysed in §6. |
| Step 5, RLC buffer | Not done, as recorded. Bufferbloat is unchanged: mean TCP downlink RTT 529–1213 ms at 2 m, 1995–2255 ms at 10 m. |

Config verified from the startup dumps: all four logs are `tx_gain 89.75` / **`rx_gain 60`**,
Location1/2/3 on TDD 2 DL : 2 UL (5-5 symbols), `Location3_TDD` on 3 DL : 1 UL (6-2). The
isolation run is properly controlled — **only** the TDD pattern differs.

---

## 1. Headline: `rx_gain 60` is spectacular at 2 m and destroys 10 m

The gate criterion from the checklist passed handsomely at Loc 1 — and then the same setting
was used for the whole campaign, where it turns out to be badly wrong at the far point
(`fig10_rxgain_tradeoff.pdf`).

Uplink, mean of TCP and UDP, same TDD pattern and placement in both campaigns:

| | rx_gain 70 (08-02) | rx_gain 60 (08-03) | |
|---|---|---|---|
| **2 m LOS** — throughput | 15.9 Mb/s | **29.3 Mb/s** | ▲ 1.8× |
| SINR / BLER | 20.5 dB / 22 % | **25.3 dB / 6 %** | |
| **5 m partition** — throughput | 5.9 Mb/s | 7.8 Mb/s | ▲ 1.3× |
| SINR / BLER | 14.2 dB / 52 % | 9.9 dB / **2 %** | |
| **10 m wall** — throughput | 15.6 Mb/s | **2.6 Mb/s** | ▼ 0.17× |
| SINR / BLER | 18.0 dB / 1 % | **1.0 dB** / 5 % | |

**A 10 dB cut in receiver gain cost 17 dB of SINR at 10 m.** More than one-for-one, because
the link went from comfortably above the noise floor to sitting on it. At 2 m the same cut
removed front-end compression and bought 4.8 dB of *real* SINR plus a 4× drop in block errors.

The full picture at `rx_gain 60`, phone-side, 3 reps each (uplink figures are the **sender**
value — see §2):

| Location | TCP DL | UDP DL | TCP UL | UDP UL |
|---|---|---|---|---|
| 2 m LOS | 22.4 | 35.8 | **26.8** | **31.7** |
| 5 m partition | 12.8 | 26.2 | 4.2 | 11.3 |
| 10 m wall | 6.9 | 9.6 | 3.5 | 1.6 |
| *4G baseline* | *26.1 / 23.8 / 10.0* | *21.8 / 22.4 / 10.5* | *13.1 / 16.0 / 12.6* | *17.2 / 15.8 / 14.1* |

At 2 m the 5G uplink is now **2× the 4G baseline** (26.8 vs 13.1 TCP, 31.7 vs 17.2 UDP) and
the downlink beats it on UDP. That is the best 5G result the project has produced, and it is
worth stating plainly in the thesis.

### The finding to actually write up

> With a fixed, manually-set receiver gain and no AGC, this gNB cannot serve the whole cell.
> `rx_gain 70` is correct at 10 m and overloads at 2 m; `rx_gain 60` is correct at 2 m and
> desensitises at 10 m. There is no single value that works, and the two campaigns bracket
> the problem from both sides.

This is a real, well-evidenced limitation of running a software RAN on a COTS SDR without
per-UE receive-gain control, and it generalises beyond this testbed. It also retro-explains
the strange non-monotonic distance behaviour in *both* campaigns.

---

## 2. A data-quality trap: `receiver` is unusable on the stalled uplink runs

At 10 m the uplink tests stalled badly — a 20 s test ran for 57–70 s, with whole seconds at
0 bits/s. On those runs the iperf3 results exchange fails and the phone reports
`receiver 0.00 bits/sec` even though the sender moved 27 MB. The server-side JSON agrees
(only 1 of 3 Loc 3 TCP uplink tests, and 2 of 3 UDP downlink tests, completed at all).

**Use the sender-side / per-second figures for uplink at Loc 3**, not the receiver summary.
`analyse_0803.py` does this automatically. Anything quoting `receiver_Mbps` for those runs
would report 0 Mb/s, which is wrong — the link carried ~3.5 Mb/s, badly.

---

## 3. The PHR "anomaly" is the PRB-allocation term, not a mystery

The session log flagged PHR reading −10 to −12 dB at `rx_gain 60` today versus −1 to 0 dB at
the same gain during the 08-02 sweep, with placement and config confirmed identical.

Power headroom in TS 38.213 §7.7.1 contains a **−10·log₁₀(M_RB)** term, so PHR falls as the
scheduler grants wider allocations. Binning every metrics report from this campaign by PRBs
per uplink slot:

| PRB per slot | n | measured PHR | −10·log₁₀(M_RB) |
|---|---|---|---|
| 2–5 | 78 | −8.3 dB | −7.0 dB |
| 5–10 | 230 | −7.0 dB | −8.4 dB |
| 10–20 | 40 | −12.3 dB | −11.4 dB |
| 20–40 | 134 | −16.4 dB | −15.1 dB |
| 40–60 | 842 | −18.1 dB | −16.9 dB |

Measured tracks predicted within ~1.5 dB across the whole range; correlation with log₁₀(PRB)
is −0.64 over 1331 reports.

The 08-02 sweep was done on an essentially idle link (small allocations → PHR ≈ 0). Today's
figures come from saturated transfers with ~46 PRB grants → PHR ≈ −13. **Same gain, same
placement, different load.** No accumulator effect needed, and nothing to chase.

Practical consequence: **PHR is only comparable between measurements at comparable PRB
allocation.** Any PHR quoted in the thesis needs the load stated alongside it.

---

## 4. The TDD isolation run — clean experiment, confounded conditions

Loc 3, `rx_gain 60`, uplink only, only `tdd_ul_dl_cfg` differing:

| | 2 DL : 2 UL | 3 DL : 1 UL |
|---|---|---|
| uplink slots granted | 800/s | 400/s |
| PUSCH SINR | **1.65 dB** | **15.05 dB** |
| uplink MCS | 0.77 | 10.17 |
| uplink BLER | 4.5 % | 5.7 % |
| PHR | −21.8 dB | −19.5 dB |
| throughput (sender, steady) | 3.50 Mb/s | **5.64 Mb/s** |
| test duration (asked 20 s) | 64 s | 38 s |

**The pattern with *half* the uplink airtime delivered *more* uplink throughput.** That is
the opposite of what airtime predicts, and the cause is visible: SINR differs by **13.4 dB**
between the two configurations at identical gain and placement.

Two things this is *not*:
- **Not PRB spreading.** Allocation size is nearly identical (46.6 vs 42.5 PRB per grant),
  worth only 0.4 dB of power-spectral-density difference.
- **Not the load-dependent PHR term of §3.** At *higher* PRB load (15.6k vs 5.7k PRB/s in
  matched time buckets) the 3:1 configuration still shows far better SINR.

Two candidate explanations, neither confirmed:
- **Handset transmit-power back-off at higher uplink duty cycle.** Doubling the uplink duty
  from 23 % to 47 % doubles the UE's average output power; handsets commonly apply
  SAR/thermal back-off under that condition. At 2 m there is ~25 dB of margin so it would be
  invisible; at 10 m with no margin it would be decisive — which matches what we see.
- **Receiver TX→RX settling.** The 2:2 pattern cuts the guard period from 6 symbols to 4
  (214 µs → 143 µs). If the B210's switching transient is comparable, the first uplink
  symbols would be corrupted.

**What this run cannot do is answer the question it was designed for.** It was meant to
separate the TDD contribution from everything else at 10 m — but it was executed at a gain
setting where the 10 m uplink is broken (§1), so both arms sit in a degraded regime. The
July→August 10 m question (open item 3 in the checklist) remains open.

**Redo it at `rx_gain 70`**, where 10 m is known to work. Same three reps, uplink only, both
patterns. That is a ~10-minute experiment and it would settle both this and the duty-cycle
hypothesis at once — if the 13 dB SINR gap persists at a gain where the link is healthy, the
effect is real and structural; if it vanishes, it was an artefact of operating at the noise
floor.

---

## 5. Everything else, briefly

- **Attach behaviour is now perfect.** One PRACH, one RRC setup, one C-RNTI, zero RLFs at all
  four sessions. Contrast with 18 re-attaches at Loc 2 in August.
- **Receiver overload is gone** as intended: `pusch_rsrp_db=ovl` appears in 0.8 % of reports
  at Loc 1 (was 7.2 %) and never at Loc 2 or Loc 3.
- **Bufferbloat is unchanged**, as expected since step 5 was skipped. Mean TCP downlink RTT
  529–1213 ms at 2 m and 1995–2255 ms at 10 m; the 6.17 MB RLC queue is untouched.
- **Uplink UDP jitter** (server side, authoritative): 6.1–7.6 ms at 2 m, 17–35 ms at 5 m,
  **87.6–115.3 ms** at 10 m. The 10 m figures are a direct consequence of §1.
- **Downlink at 2 m improved too** — TCP 16.5 → 22.4 Mb/s. Uplink quality bounds downlink TCP
  (the mechanism from `FINDINGS_RERUN_2026-08-02.md` §4), so fixing the uplink helped both.

---

## 6. Unloaded latency — the gap in the project is now filled

`ping_Loc1..3`, 30 ICMP echoes at 1 s from the core to the UE (`10.45.0.7`), no other traffic
(`fig11_unloaded_latency.pdf`):

| Location | loss | min | mean | median | p95 | max | sd |
|---|---|---|---|---|---|---|---|
| 2 m, line of sight | 0 % | **16.0 ms** | 25.0 ms | 24.6 ms | 33.7 ms | 34.9 ms | 5.9 ms |
| 5 m, partition | 0 % | **15.9 ms** | 28.1 ms | 26.7 ms | 41.6 ms | 48.5 ms | 8.8 ms |
| 10 m, concrete wall | 0 % | **15.7 ms** | 26.2 ms | 25.1 ms | 35.3 ms | 48.4 ms | 7.5 ms |

**The floor is 15.7–16.0 ms and does not change with distance.** Ten metres of air is 33 ns
each way — six orders of magnitude below the measured floor — so this is entirely the fixed
processing and scheduling pipeline: UE modem, gNB PHY/MAC, GTP-U through the UPF, and back.
Zero packet loss at every location, including through the concrete wall.

This is a respectable figure for a private 5G network built on general-purpose hardware and
an SDR, and it is the number to quote in the thesis when a reader asks what latency the
testbed achieves.

### The sawtooth, and what it says about uplink access delay

The per-echo series is not noise — it is a clean sawtooth. At 2 m, RTT walks down
27.5 → 16.0 ms in ~1.2 ms steps, jumps back up by 18.9 ms, and repeats:

```
27.5 25.9 24.1 22.9 21.0 20.0 19.0 18.1 17.8 16.1 | 34.9 33.7 32.1 31.1 29.9 28.0 …
```

The mechanism is a phase beat. The 30 echoes took 29 036 ms, i.e. the real interval is
**1001.2 ms**, not 1000. Each echo therefore arrives 1.2 ms further into the scheduling cycle
than the last, so the wait remaining until the next opportunity *shrinks* by 1.2 ms per
echo — until it runs out and the next echo has to wait a full cycle, which is the jump. The
sweep spans **≈19 ms**, which is therefore the period of the uplink scheduling opportunity
the echo reply waits for. The gNB separately reports a constant
`avg_sr_to_pusch_delay = 7.5 ms` on top of that wait.

So the latency budget decomposes as roughly **16 ms fixed + 0–19 ms waiting for an uplink
scheduling opportunity**. That is a much more useful statement for the thesis than a single
mean, and it explains why the mean (25–28 ms) sits near the middle of the range.

*(The ≈19 ms is inferred from the beat; the SR periodicity is not printed in the gNB's config
dump, so it is not read directly from configuration.)*

### Idle versus loaded — the cost of the RLC queue, in one comparison

| Location | idle | during a TCP download | inflation |
|---|---|---|---|
| 2 m | 25.0 ms | 529–1213 ms | **×35** |
| 5 m | 28.1 ms | 230–2011 ms | **×40** |
| 10 m | 26.2 ms | 1995–2255 ms | **×81** |

The radio is capable of ~16 ms. The 6.17 MB downlink RLC queue turns that into 0.5–2.3
seconds the moment a single TCP download starts. Resizing that queue (step 5, still not done)
is now clearly the highest-value remaining change — it is the difference between a testbed
that can host interactive applications and one that cannot.

---

## 7. The AMF log

`03-Aug/amf.log` covers 18:17–19:10 (the whole session). 110 info, 15 warning, 11 error lines.
Most of it is benign Open5GS NRF housekeeping — `Subscription validity expired` ×7 and the
associated NF re-registration churn.

Two entries are worth a footnote:

- **`NGReset` ×3** — one per gNB restart, matching the three location changes. Consistent.
- **`Receive Update SM context (DUPLICATED_PDU_SESSION_ID)` ×2, with `HTTP response error [500]` ×3.**
  When the gNB restarts, the AMF asks the SMF to update a PDU session the SMF still considers
  active, and the SBI call fails with HTTP 500. This is the core-side counterpart of the
  NGAP `UEContextReleaseCommand` / `PDUSessionResourceSetupRequest` race documented in
  `FINDINGS.md` §5 — the same stale-session problem, seen from the service-based interface.
  Harmless here because the UE re-attaches cleanly, but it is a genuine srsRAN/Open5GS
  interop rough edge and cheap to mention.

---

## 8. What is still missing

- **`PLACEMENT.md` and the photos** from step 0.

---

## 7. Recommended next lab session (~25 minutes)

1. **Re-run the TDD isolation at `rx_gain 70`**, Loc 3, uplink only, both patterns, 3 reps
   each (~10 min). Settles §4 and the July→August question together.
2. **Sweep `rx_gain` at Loc 3** (70 / 65 / 60), uplink only, 3 reps each (~8 min). Gives the
   far end of the gain curve, so §1's claim becomes a measured curve rather than two points.
3. **Resize the RLC queue** to ~256 kB and re-run 3 TCP downlink reps at one location
   (~5 min). Now clearly the highest-value change of the three — §6 shows it is worth
   a 35–81× latency reduction, and the radio itself is already capable of 16 ms.
   Re-run the pings alongside the downloads to measure the improvement directly.
4. Write `PLACEMENT.md`.

If a per-UE or adaptive receive-gain option exists in this srsRAN build, that is worth
investigating at the desk — §1 is otherwise an unavoidable limitation of the testbed and
should be written up as such.
