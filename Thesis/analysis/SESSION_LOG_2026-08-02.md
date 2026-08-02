# Lab session log — 2026-08-02

Written so this session can be restored in a fresh Claude Code instance. If you're that fresh
instance: read `CLAUDE.md` (repo root) and `Thesis/analysis/FINDINGS.md` first, then this file.
This file is the record of what was decided *during* today's lab session — FINDINGS.md is the
analysis of the original 24-run campaign (now with corrections inline), CLAUDE.md is the stable
project overview.

## Why this session happened

Continuing from a prior Claude Code conversation that was on a different computer (VS Code, at
home) and couldn't be recovered here (local session files, no cloud sync). Re-derived context by
re-reading `FINDINGS.md`, then went to the lab to re-run the 5G uplink tests it recommended.

## 1. Correction to FINDINGS.md — read this before trusting the original root-cause section

FINDINGS.md §3 originally claimed the 5G uplink collapse was caused by `pcg_p_nr_fr1: -15` (a
transmit-power cap) being active during the 2026-07-25 campaign. **This is wrong**, confirmed
two ways:
- The campaign's own `gnb.log` startup dump ("gNB input configuration (only non-default
  values)") has no `pcg_p_nr_fr1` line — proving it was unset during that run.
- Independently confirmed by the person who ran the tests: the line was commented out then too.

FINDINGS.md §0, §3, and the Re-run plan now all have inline correction notes (dated
2026-08-02) — the PHR/measurement data in there is still real, only the causal story attached
to it was wrong. **The real cause of the ~33 dB unexplained uplink deficit is still open.**
Leading unconfirmed hypothesis: the declared `ss-PBCH-BlockPower` (−16 dBm) and/or
`p0-NominalWithGrant` (−76 dBm) don't match the actual RF chain (antenna/cable/the unusually
high `tx_gain: 89.75`), causing the UE's path-loss estimate — and therefore its power-control
target — to be off by a constant amount at every distance. **Not verified. Needs proper
calibration equipment/time, not a lab-bench task.** Don't state this as fact in the thesis
until checked.

## 2. Config changes made today, on the actual RAN host (`gnb_n78.yaml`)

Note: this repo's `files/gnb.yaml` is a documentation/reference copy only — the live file lives
on a separate machine (the RAN host) and was edited directly there, not through this repo. The
values below are what the live file was brought to during this session; mirror them into
`files/gnb.yaml` later if useful, it's not urgent.

- `tdd_ul_dl_cfg`: was `nof_dl_slots: 3, nof_dl_symbols: 6, nof_ul_slots: 1, nof_ul_symbols: 2`
  (heavy DL-favoring, ~23% UL airtime) → changed to `nof_dl_slots: 2, nof_ul_slots: 2`. Symbols
  first tried at 4/4 (srsRAN rejected the config), settled on **5/5** (guard period drops from
  6 to 4 symbols — still ample at 2–10 m, propagation delay negligible at these ranges).
  New UL airtime ≈ 46% (up from ~23%), UL grant ceiling ≈ 800/s (up from ~400/s).
- `pcg_p_nr_fr1: -15` — commented out. (Per §1 above, this was already inactive in the original
  campaign, so this change alone doesn't explain any improvement — but correct to leave
  disabled regardless.)
- `rx_gain` — swept manually at Loc 1 (2 m), the closest/worst-case point for receiver overload:
  - `70` (original campaign's value): heavy OVL (ADC overload) flags, PHR read +4 to +8 dB but
    unreliable — clipping distorts the SINR measurement the power-control loop uses, so this
    reading doesn't reflect the true link.
  - `63`: OVL returns.
  - `60`: **clean, no OVL. PHR −1 to 0 dB.** This is the honest reading — marginal but real,
    consistent with the still-unexplained ~33 dB deficit in §1.
  - **Locked in: `rx_gain: 60`.**
- `tx_gain: 89.75` (device max) — unchanged throughout.
- `log: all_level: info, hex_max_size: 0` — `info` kept (not `warning`) because per-slot
  MCS/BLER detail is needed for the modulation-ladder analysis; `warning` was only ever a
  recommendation for continuous 24/7 operation, not a measurement campaign. `hex_max_size: 0`
  cuts log volume with no loss of anything analysis-relevant.
- `pcap: mac_enable: true, ngap_enable: true` — kept on.
- **`metrics:` block added** (new — wasn't in the original config at all):
  ```yaml
  metrics:
    enable_log: true
    enable_json: true
  ```
  Confirmed working live (see §3). `enable_json` alone would only expose a WebSocket
  (`remote_control.bind_addr`/`port`, needs a separate client script to consume) — it does NOT
  write to a file. `enable_log` is the one that matters: it routes metrics into `gnb.log`
  directly, which already has real per-line timestamps.

## 3. Key discovery: `gnb.log` now carries fully-timestamped metrics natively

With `enable_log: true`, `gnb.log` gets `[METRICS ]`-tagged lines interleaved with the normal
event log, real ISO timestamps, sub-millisecond precision. Confirmed sample from a 2026-08-02
test run:

```
2026-08-02T14:40:19.021819 [METRICS ] MAC cell pci=1 metrics: slots=[200.0, 300.0) nof_slots=2000 ...
2026-08-02T14:40:19.021830 [METRICS ] Scheduler cell pci=1 metrics: total_dl_brate=1.28Mbps total_ul_brate=1.35Mbps ...
2026-08-02T14:40:19.021842 [METRICS ] Scheduler UE ue=0 pci=1 rnti=0x4601 metrics: cqi=15 dl_ri=1.0 dl_mcs=26 dl_brate=1.28Mbps dl_nof_ok=318 dl_nof_nok=20 dl_error_rate=5% ... pusch_snr_db=4.3 pusch_rsrp_db=ovl ul_mcs=1 ul_brate=1.35Mbps ... last_phr=2 ...
```

Three tagged categories per report period, `key=value` format (not the old fixed-width table):
- `MAC cell ... metrics:` — scheduler timing/latency, probably not needed for throughput/MCS analysis.
- `Scheduler cell ... metrics:` — cell-aggregate throughput/PRB usage.
- `Scheduler UE ue=... metrics:` — **the one that matters**, equivalent of the old per-UE
  table row (`cqi`, `dl_mcs`, `dl_brate`, `dl_error_rate`, `pusch_snr_db`, `ul_mcs`, `last_phr`,
  etc.) but self-labeled key=value instead of positional columns.

This also confirms what "RSRP ovl" meant earlier in the session: `pusch_rsrp_db=ovl` is a
literal string the field is set to when the receiver is overloaded — not a console flag being
eyeballed.

**Implication:** the whole trace.log-correlation problem this session spent a long time on
(copy-paste scrollback truncation, `ts`-pipe, `wc -l` bracketing, clock-delta reconstruction)
is now moot. Just let the gNB run and slice `gnb.log` by each rep's real start/end wall-clock
time (from the CellularLab JSON or iperf3 JSON, both of which self-timestamp).

**Open TODO, not done yet:** `Thesis/analysis/scripts/parse_traces.py` still expects the OLD
fixed-width `trace.log` table format from the original campaign. It needs adapting (or a new
script) to instead grep `[METRICS ] Scheduler UE` lines out of `gnb.log` and extract the
key=value pairs. Not urgent — the raw data is being captured correctly regardless of when the
parser catches up.

## 4. Final test methodology for the 2026-08-02 re-run

- 3 reps × 20 s iperf3 per test condition, for 3 locations × 2 protocols (TCP/UDP) × 2
  directions (DL/UL) = 12 conditions × 3 reps = 36 reps total for 5G.
- **4G is not being re-tested.** Original n=1 4G baseline stands untouched — state explicitly
  in the thesis methodology that 5G is mean±spread over 3 reps while 4G is a single reference
  run, and why (4G wasn't the subject of the fix; re-running it doesn't add information; 4G's
  own SINR/PHR were already tightly clustered in the original campaign).
- **gNB restart policy:** do NOT restart between reps, and do NOT restart when changing
  protocol or direction — both are pure iperf3/CellularLab-side choices (TCP vs UDP, normal vs
  `-R` reverse) with zero relation to the RAN config. Only restart when physically moving to a
  new location, and even that isn't strictly required (just a convenient checkpoint) —
  reasoning: avoids reattach overhead × 36 and avoids resetting power-control convergence
  between reps, which would work against using 3 reps to get a stable mean.
  So in practice: gNB up continuously for a whole location's 12 reps, restarted (or not) only
  at location boundaries.
- **Analysis note:** trim the first ~3–5 s of each 20 s TCP rep before computing steady-state
  mean (ramp-up), consistent with how the original campaign's "steady-state window" was
  defined — needed for apples-to-apples comparison with the old numbers.
- **Reporting:** mean + min–max (or ±std, explicitly labeled) over 3 reps; show the 3
  individual points in tables/figures; n=3 is a spread, not a confidence interval.
- **Methodology caveat for the thesis:** the power-cap-disable and the TDD-rebalance were both
  applied at once (not isolated across separate runs), so the resulting improvement this
  campaign measures is a *combined* effect — don't present it as isolating either factor's
  individual contribution. An optional supplementary run (TDD reverted to 3:1, power-cap-fix
  still in place, UL only) would let you split the two empirically, if time allows.

## 5. Data capture plan

- **Phone (Samsung Z Flip 5, CellularLab):** exports one JSON per rep already, includes
  reverse-mode (`-R`) for DL, self-timestamped. No extra work needed.
- **iperf3 server (core, Ubuntu):** run **persistent per location** (not restarted per rep, to
  cut walking time between UE and core machine):
  ```bash
  iperf3 -s --json --logfile <Location>.json
  ```
  (no `-1` flag) — left running for all 12 reps at that location, restarted only at location
  change, alongside the gNB.
  **Gotcha:** without `-1`, each completed test appends its own full JSON object with no
  wrapping array or separator — the resulting file is **concatenated JSON, not a single valid
  JSON document**. `json.load()` on the raw file will fail. Post-process with:
  ```bash
  jq -s '.' Loc1_2m.json > Loc1_2m_array.json
  ```
  (slurp mode) or a Python loop using `json.JSONDecoder().raw_decode()` advancing position each
  time. Each object already carries its own `start.timestamp` — no manual bookkeeping needed to
  pair it with the CellularLab JSON or gnb.log, just match timestamps.
  Rationale for capturing server-side at all: for DL tests the phone is the receiver and the
  core is the TCP sender — retransmission/cwnd stats are most reliably read from the sender
  side, i.e. the server's JSON, not the phone's.
- **`gnb.log`:** continuous per location (or longer), real timestamps as of §3 — slice by each
  rep's known start/end wall-clock time directly, no bracket/restart needed for this.
- **pcaps (mac/ngap):** continuous, real per-packet timestamps, filter by time as needed.
- **Folder convention (unchanged):** `Thesis/testing_data/5G/Loc_<n>_<dist>m/<TCP|UDP>/<DL|UL>/`
  — each folder now holds 3 reps' worth of phone-JSON, plus a reference to (or time-sliced
  extract from) the shared per-location `gnb.log` / iperf3-server JSON / pcaps, rather than
  fully separate files per rep for those three.

## 6. Open items for later (not lab-bench tasks)

- Investigate the real cause of the ~33 dB uplink deficit (§1) — `ss-PBCH-BlockPower` /
  `p0-NominalWithGrant` calibration vs actual RF chain is the leading unconfirmed hypothesis.
- Adapt/rewrite `parse_traces.py` (or add a new script) for the new `[METRICS ]` key=value
  format in `gnb.log` (§3) — old script only understands the original `trace.log` table.
- Optional: an isolating supplementary run (TDD back to 3:1, power-fix still in place, UL only)
  to split the combined effect noted in §4 into its two components.
- Mirror the final `gnb_n78.yaml` settings (§2) into this repo's `files/gnb.yaml` when
  convenient — not urgent, that file is documentation only.
- Verify NTP/clock sync between phone and RAN host if any timestamp-based analysis later seems
  off (network has internet, phone auto-syncs — flagged as resolved, not expected to be an
  issue, but worth a sanity check if numbers look wrong).
