# Lab checklist — next 5G session

Self-contained handoff. Written 2026-08-03, after analysing the 2026-07-25 campaign
(24 runs, 4G + 5G) and the 2026-08-02 5G re-run (39 reps).

**If you are a fresh Claude instance loading this at the lab:** this file is enough to work
from. For depth, read in this order — `CLAUDE.md` (repo root, project overview) →
`Thesis/analysis/FINDINGS.md` (original campaign, has inline corrections) →
`Thesis/analysis/FINDINGS_RERUN_2026-08-02.md` (the re-run; §7–8 are the newest) →
`Thesis/analysis/SESSION_LOG_2026-08-02.md` (what was decided in the last lab session).
Analysis scripts are in `Thesis/analysis/scripts/`, extracted data in
`Thesis/analysis/data/`, figures in `Thesis/analysis/figures/`.

---

## 1. Testbed state as of the last session

### 5G (the system under test)

RAN host is a separate machine; `files/gnb.yaml` in this repo is **documentation only** —
the live file is `gnb_n78.yaml` on the RAN host and must be edited there.

| | Value |
|---|---|
| Software | srsRAN Project gNB, commit `29dc1aede7`, branch `dev` |
| SDR | USRP **B210** via UHD (`device_args: type=b200` is the UHD family string, not the model) + Leo Bodnar GPSDO, `clock: external`, `sync: external` |
| RF front end | **none** — no external LNA or PA |
| Band / centre | n78 TDD, `dl_arfcn: 627340` = **3410.1 MHz** |
| Bandwidth | 20 MHz, `common_scs: 30`, 51 PRB, `pci: 1` |
| TDD pattern | `dl_ul_tx_period: 5`, `nof_dl_slots: 2`, `nof_dl_symbols: 5`, `nof_ul_slots: 2`, `nof_ul_symbols: 5` → 47.1 % DL / 47.1 % UL / 4 symbols guard |
| Gains | `tx_gain: 89.75` (device max), **`rx_gain: 70`** |
| `pcg_p_nr_fr1` | commented out (and was already inactive during the July campaign — verified) |
| Sample rate | `srate: 23.04`, `otw_format: sc12` |
| Logging | `all_level: info`, `hex_max_size: 0`, `high_latency_diagnostics_enabled: true` |
| Metrics | `metrics: {enable_log: true, enable_verbose: true, autostart_stdout_metrics: true}` |
| pcap | `mac_enable: true`, `ngap_enable: true` |
| DRB1 DL RLC AM | `queue_size=16384`, **`queue_size_bytes=6172672` (6.17 MB)**, `t_poll_retx=100`, `max_retx=32`, `poll_pdu=16` |
| Core | Open5GS 5GC, AMF `10.0.0.10:38412`, gNB binds `10.0.0.20`, PLMN `00101`, TAC 7 |
| Data plane | iperf3 server at **`10.45.0.1:5201`**, UE gets `10.45.0.x` |
| UE | Samsung Galaxy Z Flip 5, CellularLab app |

### 4G baseline — **do not re-run**

n=1 reference from 2026-07-28, deliberately left untouched: srsRAN 4G `srsenb` @ `6bcbd9e5b`,
Nuand bladeRF xA4 via SoapySDR **with BT-100 RX LNA and BT-200 TX amp**, Band 7 FDD
(DL 2680 / UL 2560 MHz), 10 MHz / 50 PRB, Open5GS EPC.

### Locations

| | Distance | Obstruction |
|---|---|---|
| Loc 1 | 2 m | clear line of sight |
| Loc 2 | 5 m | office partition |
| Loc 3 | ~10 m | concrete wall |

---

## 2. Where things stand

### Established

- **The uplink pathology from July is gone.** 5G UL now matches the 4G baseline: 12.6 vs
  13.1 Mb/s at 2 m, 11.6 vs 12.6 Mb/s at 10 m (was 5.1 and 0.58).
- **The downlink loss is exactly the airtime traded away.** Scaling July's numbers by the
  TDD change (DL ×0.69) predicts the August UDP downlink within 1 % at 10 m and 14 % at 2 m.
  Clean, defensible TDD capacity trade.
- **Link adaptation over-reaches near the radio.** The gNB grants the full 800 UL slots/s
  everywhere, but only 619/800 decode at 2 m (22 % BLER, MCS 18.5) and 369/800 at 5 m
  (53 % BLER) versus 787/800 at 10 m (1.3 % BLER, MCS 12.1) — while reporting 18–20 dB SINR
  at both 2 m and 10 m. `pusch_rsrp_db=ovl` fires in 7.2 % of reports at Loc 1, 1.9 % at
  Loc 2, never at Loc 3. Strong evidence for receiver front-end compression at `rx_gain 70`.
- **Multi-second bufferbloat on the downlink.** At 10 m, TCP RTT climbs 401 ms → 6542 ms over
  a 20 s transfer with **zero retransmissions**. The gNB's `dl_bs` peaks at 6.15 MB against a
  configured RLC queue of 6.17 MB — the queue fills to 99.9 % of its limit.

### Open

1. **`rx_gain 60` was never applied.** The last session's sweep concluded on it, but all three
   August logs show `rx_gain: 70`. The fix is untested.
2. **Loc 2 (5 m) data is unusable** — 18 PRACH attempts, 18 distinct C-RNTIs (0x4601–0x4612),
   9 RLF-triggered releases (`MAC max consecutive CRC KOs`). One rep returned 0.00 Mb/s.
3. **The 10 m uplink improved 22 dB between campaigns**, ~10× more than the TDD change can
   explain. Loc 1 and Loc 2 moved only ~5 dB. Physical placement probably differed, but it
   was never documented, so this cannot currently be claimed either way.
4. **No unloaded latency measurement exists** for the testbed.

---

## 3. The checklist

Total ~1 hour. **Step 1 is a decision gate — do it before committing to anything else.**

### Step 0 · Document the geometry — 10 min · do this BEFORE moving anything

- [ ] Photograph the antenna and the UE position at each of the three locations
- [ ] Tape-measure UE↔antenna distance; note both heights
- [ ] Note antenna orientation/polarisation and UE orientation (screen facing where?)
- [ ] Note anything in the path (partition, wall, furniture, people)
- [ ] Save as `Thesis/testing_data/<campaign>/PLACEMENT.md` + photos

Rationale: open question 3 exists purely because this was never recorded. Ten minutes here
protects every measurement that follows.

### Step 1 · rx_gain sweep at Loc 1, uplink only — 15 min · **GATE**

Loc 1 is the worst case for receiver overload (closest UE, strongest received signal).

- [ ] gNB at `rx_gain: 70`, 3 reps TCP UL — reproduce the baseline
- [ ] `rx_gain: 65`, restart gNB, 3 reps TCP UL
- [ ] `rx_gain: 60`, restart gNB, 3 reps TCP UL
- [ ] `rx_gain: 55`, restart gNB, 3 reps TCP UL

Phone command (CellularLab), unchanged from last campaign:
```
iperf3 -c 10.45.0.1 -p 5201 -t 20 -i 1 -P 8 -d -V
```

**Check against these numbers as you go** (from `[METRICS ] Scheduler UE` in `gnb.log`):

| | at rx_gain 70 (known) | what you want to see |
|---|---|---|
| `ul_error_rate` | ~22 % | **single digits** |
| `ul_nof_ok` / total | 619 / 800 | **~780 / 800** |
| `ul_mcs` | 18.5 | ≥ 18 |
| throughput | 12.6 Mb/s | **16–20 Mb/s** |
| `pusch_rsrp_db` | `ovl` in ~7 % of reports | never `ovl` |

Ceiling for reference: 800 grants/s × 51 PRB ≈ 25–30 Mb/s, so 16–20 is reachable.

**Decision rule:**
- **BLER drops materially** → the diagnosis is confirmed. Lock in the best gain and budget
  ~40 more minutes to re-run the full matrix (12 conditions × 3 reps) at that gain, because
  the August campaign is then "the wrong gain" campaign.
- **BLER doesn't move across the whole sweep** → it is not the receiver. Skip the full re-run,
  and note UE PA compression / outer-loop link adaptation as the remaining suspects. Move on
  to step 2 with `rx_gain 70`.

### Step 2 · Re-measure Loc 2 (5 m) — 12 min

At whichever gain step 1 selected. Full 12 reps: TCP/UDP × DL/UL × 3.

- [ ] Watch for re-attaches — `rg -c "CCCH UL rrcSetupRequest" gnb.log` should be **1**, not 18
- [ ] Expect 5 m to land *between* 2 m and 10 m on every metric (it currently doesn't)

If it is still unstable at a clean gain, the cause is location-specific — spend 5 minutes
checking for interference (does the instability persist if you move 1 m either way?) rather
than assuming a config fault.

### Step 3 · TDD isolation at Loc 3 — 8 min · highest information content

Revert `tdd_ul_dl_cfg` to the **July** pattern, uplink only, 3 reps, at the placement you
documented in step 0:

```yaml
tdd_ul_dl_cfg:
  dl_ul_tx_period: 5
  nof_dl_slots: 3
  nof_dl_symbols: 6
  nof_ul_slots: 1
  nof_ul_symbols: 2
```

**Interpretation, decided in advance:**
- **~0.5–0.6 Mb/s** → July reproduces; placement was the same; the TDD change genuinely
  delivered ~20×, which is 10× more than airtime explains and needs a mechanism.
- **~5–6 Mb/s** (half of 11.6, exactly the airtime factor) → the July 10 m measurement was
  faulty or the placement differed; the TDD change accounts for exactly 2× and nothing more.

Either result is publishable. Restore the 2 DL : 2 UL pattern afterwards.

### Step 4 · Unloaded latency — 3 min

With **no** iperf3 running, from the core:
```
ping -c 60 -i 1 10.45.0.<UE>   # save output per location
```
- [ ] Loc 1  - [ ] Loc 2  - [ ] Loc 3

Expect 10–30 ms. Anything much higher is itself a finding. This fills a real gap: all current
RTT data is under a saturating 8-stream load.

### Step 5 · The RLC buffer — 10 min

Cut the DRB downlink RLC AM queue from 6.17 MB to ~256 kB, in the `qos` → `rlc` → `am` → `tx`
block of the live config. **Verify without running a test** — the gNB prints the effective
values at DRB setup:

```
rg "DRB1 DL: RLC AM configured" /tmp/gnb.log
# want: queue_size_bytes≈262144   (was 6172672)
```

Then 3 TCP DL reps at Loc 3.

| | before | expect |
|---|---|---|
| mean RTT | 2.66 s | **0.2–0.3 s** |
| max RTT | 6.70 s | < 0.5 s |
| throughput | 9.4 Mb/s | roughly unchanged |

256 kB is ~3× the bandwidth-delay product at these rates, so 8 streams should still fill the
pipe. If throughput drops materially, try 512 kB — you'll have measured the trade-off curve,
which is a better result than either endpoint alone.

### If you only get 20 minutes

**Steps 0, 1 and 3.** Those three resolve every claim in the analysis that is currently
unsupported. Everything else is refinement.

---

## 4. Capture conventions

Keep what worked last time:

- **gNB:** up continuously for a whole location's reps. Do **not** restart between reps or
  when switching protocol/direction — those are pure iperf3-side choices and restarting
  resets power-control convergence. Restart only at location boundaries and config changes.
- **`metrics: enable_log: true`** + `hex_max_size: 0` + `all_level: info`. This combination
  put fully-timestamped `[METRICS ] Scheduler UE` lines straight into `gnb.log` and made the
  analysis far easier than the July campaign's fixed-width `trace.log`. Keep it.
- **iperf3 server — use a distinct logfile per location:**
  ```bash
  iperf3 -s --json --logfile Loc1_2m.json
  ```
  `--logfile` **appends**; restarting the server does not clear it. Reusing one path is why
  the August `test.json` files each contained every earlier location's runs.
  The result is concatenated JSON, not an array — `json.load()` fails. Parse with
  `jq -s '.' Loc1_2m.json > Loc1_2m_array.json`, or `json.JSONDecoder().raw_decode()`.
  Capture server-side regardless of direction: for downlink tests the core is the TCP
  *sender*, so RTT / `snd_cwnd` / `retransmits` only exist there.
- **Phone exports:** name them `<PROTO>_<DIR><rep>.txt` (`TCP_DL1.txt` …) at capture time if
  you can. If they come out as `iPerf3_<timestamp>_v2.2_1.txt`, run
  `scripts/rename_reps.py --apply` afterwards — it classifies from the iperf3 command line
  inside each file and writes a `rename_manifest.csv` preserving the originals.
- **Folder convention:** `Thesis/testing_data/<campaign>/Loc<n>_<dist>m/`
- **Analysis window:** drop the first 5 s of each 20 s rep (TCP ramp-up) before computing
  steady-state means — consistent with how both campaigns have been processed.
- **Reporting:** mean + min–max over 3 reps, showing the individual points. n=3 is a spread,
  not a confidence interval. State explicitly that 4G is a single reference run and why.

---

## 5. Reference numbers to check against at the bench

**5G, 2026-08-02** (mean over reps; Loc 2 unusable):

| | 2 m | 5 m | 10 m |
|---|---|---|---|
| TCP DL | 16.5 | *16.4* | 4.6 |
| UDP DL | 36.3 | *22.0* | 19.0 |
| TCP UL | 12.6 | *3.3* | 11.6 |
| UDP UL | 15.3 | *4.3* | 14.2 |
| UL grants ok/800 | 619 | *369* | 787 |
| UL BLER | 22 % | *53 %* | 1.3 % |
| UL MCS | 18.5 | *17.0* | 12.1 |
| PUSCH SINR | 20.5 dB | *14.2 dB* | 18.0 dB |
| PHR | −2.0 dB | *−13.2 dB* | −16.2 dB |
| TCP DL mean RTT | 470 ms | *1.20 s* | 2.66 s |
| gNB `dl_bs` max | 3.30 MB | *6.15 MB* | 4.66 MB |

**4G baseline, 2026-07-28** (n=1, Mb/s): 2 m — DL 26.1 TCP / 21.8 UDP, UL 13.1 / 17.2 ·
5 m — 23.8 / 22.4, 16.0 / 15.8 · 10 m — 10.0 / 10.5, 12.6 / 14.1

**5G before, 2026-07-25** (n=1, Mb/s): 2 m — DL 29.6 / 46.3, UL 5.1 / 4.6 ·
5 m — 32.8 / 50.6, 4.4 / 0.8 · 10 m — 10.3 / 27.7, 0.58 / 0.54

---

## 6. After the session

```bash
# from Thesis/analysis/scripts/ , with pandas + numpy + matplotlib available
python rename_reps.py --apply        # if phone exports are timestamp-named
python parse_new_iperf.py            # phone exports    -> new_iperf_reps.csv
python parse_new_metrics.py          # [METRICS] lines  -> new_metrics.csv
python analyse_new.py                # joins the two, old-vs-new comparison
python inspect_new.py                # per-rep detail, session drift
python test_ovl_hypothesis.py        # the SINR/BLER inversion — rerun to test step 1
python analyse_server_json.py        # server JSON -> RTT / cwnd / retransmits / jitter
python figures_new.py                # fig7, fig8
python figures_latency.py            # fig9
```

Update paths at the top of each script if the campaign folder name changes — they point at
`Thesis/testing_data/5G_new_methodology/`.

Then write results into `FINDINGS_RERUN_<date>.md` and record what was changed on the live
RAN host in a new `SESSION_LOG_<date>.md`, following the existing files' structure.
