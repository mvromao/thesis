# Thesis project: open-source 5G testbed

MSc dissertation building and evaluating a private 5G Standalone (SA) network on open-source
software, benchmarked against a 4G baseline built on the same core hardware.

## Stack

- **5G RAN:** srsRAN Project gNB (OCUDU), USRP B210 + Leo Bodnar GPSDO, band n78 (3410.1 MHz),
  20 MHz / 30 kHz SCS, TDD.
- **4G RAN:** srsRAN 4G `srsenb`, Nuand bladeRF xA4, band 7 FDD (DL 2680 / UL 2560 MHz), 10 MHz,
  with a BT-200 LNA (RX) and BT-100 amp (TX) that the 5G rig lacks.
- **Core:** Open5GS (5GC for 5G, EPC for 4G), same physical machine for both campaigns.
- Configs live in `files/*.yaml` (`gnb.yaml`, `amf.yaml`, `smf.yaml`, `upf.yaml`, `nrf.yaml`) and
  are pushed to the core host's `/etc/open5gs` via `deploy_open5gs_configs.sh` (sparse-checkout
  from GitHub, no local credentials needed on the lab machine).
- Thesis document is LaTeX under `MSc_thesis/` (NOVAthesis template, build via `MSc_thesis/.Build/`).

## Test data & analysis

- `Thesis/testing_data/` — 24 raw test runs: 2 technologies × 3 distances (`Loc_1_2m`,
  `Loc_2_5m`, `Loc_3_10m`) × {TCP,UDP} × {DL,UL}. ~2.8 GB of srsRAN stack traces, console metric
  traces, MAC/NGAP pcaps. Folder convention: `<4G|5G>/Loc_<n>_<dist>m/<TCP|UDP>/<DL|UL>/`.
- `Thesis/analysis/scripts/` — reproducible parsing/analysis pipeline (`parse_traces.py`,
  `analyse.py`, `scan_events.py`, `scan_phy.py`, `control_plane.py`, `harq_check.py`,
  `figures.py`). Run from any directory; paths inside are absolute to `Thesis/testing_data/`.
- `Thesis/analysis/FINDINGS.md` — **the current source of truth on testbed status.** Full
  write-up of what the first 24-run campaign showed, root-cause analysis, and a concrete
  re-run plan. Read this before making any RAN config changes or drawing conclusions from data.
- `Thesis/analysis/SESSION_LOG_2026-08-02.md` — first re-run lab session: the correction to
  FINDINGS.md's root cause, config changes made on the live RAN host, the discovery that
  `gnb.log` carries native timestamped metrics, the finalized test methodology.
- `Thesis/analysis/FINDINGS_RERUN_2026-08-02.md` — home analysis of that session's data
  (39 reps). Found the uplink pathology mostly gone, but `rx_gain` had silently reverted to 70
  (never actually applied at 60), Loc 2 data unusable, a 22 dB unexplained uplink jump between
  campaigns, and multi-second downlink bufferbloat from an oversized RLC queue.
- `Thesis/analysis/LAB_CHECKLIST_next_session.md` — the resulting checklist (rx_gain sweep
  gate, Loc 2 re-measure, TDD isolation at Loc 3, unloaded-latency ping, RLC buffer resize).
- `Thesis/analysis/SESSION_LOG_2026-08-03.md` — **read this before continuing any in-progress
  work.** Execution of that checklist: `rx_gain: 60` confirmed and locked in (decisive BLER/MCS/
  OVL improvement), full re-run matrix done, TDD isolation test run at Loc 3 (result not yet
  read out of the data), pings done at all 3 locations, RLC buffer step not reached. Has a new
  unresolved PHR anomaly and a full open-items/next-steps list. Data is on a USB flash drive,
  not yet copied into `Thesis/testing_data/`.

## Known issue (as of the last campaign, 2026-07-25/28) — corrected 2026-08-02

The 5G uplink was badly regressed vs 4G (up to 21× worse at 10 m). **The original write-up
attributed this mainly to a `pcg_p_nr_fr1: -15` power cap in `files/gnb.yaml` — this was
wrong.** Verified directly from the campaign's `gnb.log` startup dump ("only non-default
values" listing has no `pcg_p_nr_fr1` line): the cap was never active during that campaign,
confirmed independently by whoever ran the tests. FINDINGS.md §3 has the correction inline;
the ~33 dB unexplained uplink deficit it originally found is real but its cause is now open —
leading unconfirmed candidate is a miscalibrated `ss-PBCH-BlockPower`/`p0-NominalWithGrant`
relative to the actual RF chain (gain staging was pushed to tx_gain 89.75/rx_gain 70, device
max, for reasons not yet tied to a specific root cause).

What's still solid:
1. TDD pattern (`tdd_ul_dl_cfg`) was 3 DL : 1 UL slots — a 2.5× structural ceiling on uplink
   airtime, inherited from an old worked example and never revisited. Changed during the
   2026-08-02 lab session to a balanced 2 DL : 2 UL pattern (5/5 symbols in the partial slot).
2. Gain staging (tx_gain 89.75, rx_gain 70) causes receiver overload (OVL) at 2 m once the UE
   is allowed to transmit at full power — confirmed live on 2026-08-02. A gain sweep at Loc 1
   found rx_gain 60 clears overload; PHR at that setting is only marginal (−1 to 0 dB) even at
   2 m, which is the strongest evidence yet that the real bottleneck isn't the (nonexistent)
   power cap but something in the link budget/calibration.
3. No RX LNA on the 5G side, no incremental redundancy on UL HARQ (`rv=0` only) — unaffected
   by the correction above, still valid secondary factors.

FINDINGS.md §"Re-run plan" has the fix-and-remeasure procedure; treat the "remove the power
cap" framing in there as superseded (see the note at the top of that section) but the TDD
rebalance and gain-sweep steps as still valid — they were carried out on 2026-08-02. Treat the
existing 24-run dataset as the "as-deployed" baseline to keep, not to discard.
