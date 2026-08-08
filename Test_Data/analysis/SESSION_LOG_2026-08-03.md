# Lab session log — 2026-08-03

Written at the end of the lab session, from the checklist in `LAB_CHECKLIST_next_session.md`
(itself written earlier the same day, after analysing the 2026-07-25 and 2026-08-02 campaigns).
Read that file for full context on why each step below was done. This file records what
actually happened when the checklist was executed.

**Data location:** everything from today (gnb.log, per-location iperf3 server JSON, phone
CellularLab exports, ping `.txt` files) is saved to a USB flash drive — not yet copied into
`Thesis/testing_data/` in this repo checkout. Do that before running any analysis scripts.

## What was done, in order

### Step 1 — rx_gain sweep at Loc 1, UL only — DONE, gate passed

Swept `rx_gain` at Loc 1 (2 m) with everything else unchanged from the August config (TDD
still 2 DL : 2 UL / 5-5 symbols, `tx_gain: 89.75`). Landed on **`rx_gain: 60`**, confirmed
against the checklist's target table:

| | rx_gain 70 (August) | target | rx_gain 60 (today) |
|---|---|---|---|
| `ul_error_rate` | ~22% | single digits | **~5%**, rare jumps to ~50% |
| `ul_nof_ok`/800 | 619 | ~780 | **760–780** |
| `ul_mcs` | 18.5 | ≥18 | **22–27** |
| `pusch_rsrp_db=ovl` | ~7% of reports | never | **1 flag total** |

Decisive improvement on every metric the gate was keyed on → **`rx_gain: 60` locked in**,
proceeded to the full re-run matrix.

**Open anomaly, not resolved today:** PHR at `rx_gain 60` today read **−10 to −12 dB**, versus
**−1 to 0 dB** for the same `rx_gain: 60` during the 2026-08-02 sweep. User confirmed identical
UE/RAN placement and confirmed no other config changed besides `rx_gain`. So this isn't
explained by placement drift or a config mismatch — the two most likely explanations checked so
far. Remaining candidate, unconfirmed: the closed-loop power-control accumulator (TPC command
history) can differ between separate sessions even at identical placement/config, since PHR
depends on accumulated state, not just instantaneous path loss. **Worth investigating at home if
time allows — check whether `last_phr` in `gnb.log`'s `[METRICS]` lines trends over the session
(converging from a different starting point) rather than being flat, which would support the
accumulator explanation.** Doesn't block anything — the gate's actual pass/fail criteria (BLER,
grants, MCS, OVL) all cleared independent of this.

### Full re-run matrix at rx_gain 60 — DONE

3 locations (including Loc 2 — confirmed by user) × 2 protocols × 2 directions, "24 tests"
reported. **Note for whoever processes this at home:** the original plan was 3 reps per
condition (36 total for 12 conditions); 24 suggests either 2 reps/condition or a different
count — verify against the actual file count before assuming which, and update the reps-per-
condition figure in whatever replaces `LAB_CHECKLIST_next_session.md`'s targets.

Whether Loc 2's specific August failure mode (18 PRACH attempts / reattaches, one 0.00 Mb/s
rep) is actually fixed this time needs verification — check `gnb.log` for repeated
`CCCH UL rrcSetupRequest` at Loc 2; should be 1, not 18, per the checklist's own check.

### Step 3 — TDD isolation at Loc 3 — DONE, result not yet reviewed

Reverted `tdd_ul_dl_cfg` to the July pattern (`nof_dl_slots: 3, nof_dl_symbols: 6,
nof_ul_slots: 1, nof_ul_symbols: 2`), 3 reps UL only, at the same placement. **User confirmed
the 2 DL : 2 UL / 5-5 pattern was restored afterward** — the gNB was not left on the reverted
config.

**The actual throughput number from this test was not reviewed during the session** — user
deferred that to the at-home analysis. This is the single most important number to pull out of
today's data first: it decides between the two pre-committed interpretations in
`LAB_CHECKLIST_next_session.md` §3 Step 3:
- **~0.5–0.6 Mb/s** → July reproduces at this placement; the 2 DL:2 UL change's uplink
  improvement is genuinely ~20×, ~10× more than the TDD airtime change alone explains, and
  needs a mechanism beyond airtime.
- **~5–6 Mb/s** (half of the corrected-config value, 11.6 Mb/s) → exactly the airtime factor;
  TDD alone explains it, and July's original 0.58 Mb/s number was likely a fluke or a different
  (undocumented) placement.

Either result is a clean, publishable finding — this just needs someone to actually read the
number off the parsed data.

### Step 4 — unloaded latency (ping) — DONE

Run from the core (correct choice — measures the same core↔gNB↔UE path the throughput tests
use; the RAN host isn't on a routable path to the UE's PDU session IP). All three locations,
saved to files. Exact ping count/duration used wasn't confirmed in this session (suggested
`-c 60 -i 1`, ≈60s per location, but user may have used a shorter count) — check the files
themselves for the actual `-c` used.

### Step 0 — geometry documentation — status unclear

User confirmed placement was identical to the 2026-08-02 session ("same exact spot"), which is
good enough to explain away the PHR anomaly candidate of placement drift — but it's not
confirmed whether the formal photograph/measurement/`PLACEMENT.md` from Step 0 was actually
produced this session. Check for a `PLACEMENT.md` on the flash drive; if it's not there, the
open question about the July→August 10 m uplink jump (§2 open item 3 in the checklist) still
has no documented geometry to fall back on for *future* sessions, even though today's own
internal comparison (Aug-02 vs Aug-03 at the same spot) is fine without it.

### Step 5 — RLC buffer resize — NOT DONE

Explicitly deprioritized due to time. Lowest-priority item in the checklist; still open for a
future session. The 6.17 MB DRB1 DL RLC AM queue causing multi-second bufferbloat at 10 m is
still unaddressed.

## Open items carried forward

1. **PHR anomaly** (this session, §"Step 1" above) — unresolved, candidate is closed-loop TPC
   accumulator history, not placement or config.
2. **TDD isolation result** (Step 3) — needs to be read from the parsed data; decides a
   significant open claim about the magnitude of the TDD fix's contribution.
3. **Loc 2 fix verification** — confirm the reattach/churn pathology from August is actually
   gone in today's data, not just assumed from having re-run it.
4. **Reps-per-condition count** for the "24 tests" — verify against actual files.
5. **Step 0 formal documentation** — check whether `PLACEMENT.md` + photos exist; if not, still
   an open gap for future placement-dependent comparisons (today's own comparison is fine
   without it, since placement was directly confirmed unchanged).
6. **Step 5 (RLC buffer resize)** — not attempted, carry to next session.
7. **The original ~33 dB uplink deficit's real cause** (from `FINDINGS.md` §3's correction,
   2026-08-02) — `ss-PBCH-BlockPower`/`p0-NominalWithGrant` calibration vs actual RF chain,
   still unconfirmed, unrelated to today's work specifically but still on the list.

## Next steps (at home, with the analysis pipeline)

1. Copy everything off the flash drive into `Thesis/testing_data/<new campaign folder>/`.
2. Run the existing pipeline (`rename_reps.py`, `parse_new_iperf.py`, `parse_new_metrics.py`,
   `parse_server_json.py`, `analyse_new.py`, `analyse_server_json.py`, `inspect_new.py`,
   `test_ovl_hypothesis.py`) — update the campaign folder path at the top of each script.
3. Pull the Step 3 TDD-isolation number first (open item 2) — it's the highest-value unresolved
   question from today.
4. Verify Loc 2 (open item 3) and check for a `last_phr` trend within the session to chase the
   PHR anomaly (open item 1), time permitting.
5. Write `FINDINGS_RERUN_2026-08-03.md` (or extend the 08-02 one) with the results, following
   the existing files' structure — and update `CLAUDE.md`'s pointer to whichever is newest.
