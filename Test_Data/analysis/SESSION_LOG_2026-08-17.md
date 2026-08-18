# Session 2026-08-17 — analysis pipeline rebuilt from scratch

Desk session, no lab. Goal was to work out what data the Results chapter needs
and start separating the `[METRICS ]` lines out of the gNB logs. Ended up
rebuilding the whole analysis pipeline, because none of it ran any more.

## Why the rebuild happened

All 19 scripts in `analysis/scripts/` hardcode
`d:/Documents/Thesis/thesis/Thesis/testing_data/…`. That path no longer exists —
the data is under `Test_Data/testing_data/` and the round folders were renamed to
`1 - 28-Jul`, `2 - 02-Aug`, `3 - 03-Aug`. **Nothing in `analysis/data/` could be
regenerated from raw.** The old scripts and CSVs are left untouched as the
regression baseline.

## What exists now

`analysis/pipeline/` — one parameterised pipeline, pure standard library
(`openpyxl` only for the Excel export). Three stages plus two reading aids:

```
cd Test_Data/analysis
python -m pipeline.extract --all --jobs 4    # raw logs -> extracted/   (~150 s)
python -m pipeline.build_tables              # -> data_v2/*.csv
python -m pipeline.compare_baseline          # regression gate vs data/
python -m pipeline.to_excel                  # -> data_v2/tables.xlsx
python -m pipeline.unpack                    # -> extracted_csv/ (plain CSV)
```

- **6.56 GB of logs → 963 KB extracted.** `[METRICS ]` is 0.02–0.08 % of a gNB log.
- **Regression gate passes 115/115** against the pre-rebuild CSVs, so every
  number already in FINDINGS*.md and DATA_INVENTORY.md remains citable.
- Registry resolves **31 log units / 102 repetitions** and reads each campaign's
  radio config from the log's own startup dump.

## Documents written

| File | What it is |
|---|---|
| `RESULTS_DATA_MAP.md` | **Start here.** One entry per §1–§11 stub in `6 - Results.tex`: comparison axis, exact file and column, verified numbers, caveat to state. |
| `COLUMNS.md` | One-line meaning for every column in every table. |
| this file | Where the session got to. |

## Newly available that wasn't before

- `Scheduler cell` metrics parsed → `data_v2/tdd_airtime.csv`. **§2's TDD airtime
  argument is now measured, not inferred**: `pusch_rbs_per_tdd_slot_idx` shows
  uplink PRBs only in slots 3–4 at 2DL:2UL, only slot 4 at 3DL:1UL.
- `MAC cell` metrics parsed → `data_v2/realtime.csv`. Second, distinct
  real-time measurement for §9 (slot wall-clock latency vs the 500 µs budget),
  alongside the existing PHY decode time.
- `mod_series.csv.gz` per unit — **modulation ladder over time**, from the PHY
  `mod=` field. Use this, not mean `dl_mcs`, for the adaptation figure.
- `logging_cost.csv` across all 31 runs: **1.4–21.5 GB/hour**, median 5.7 —
  wider than the single ~7.5 GB/h figure previously quoted.

## Findings worth folding into the chapter

1. **§5 gains independent evidence.** At the same distance and config, 5G TCP DL
   sits at 9.0 % 256QAM against UDP DL's 86.7 %. The per-second ladder shows TCP
   stepping down to 64QAM within ~2 s of sustained load and staying pinned. The
   uplink-ACK bottleneck is visible in the modulation ladder, not just in BLER.
2. **§3 PHR should be reported as a residual.** `last_phr_db` contains a
   −10·log₁₀(M_RB) term, so a wider grant lowers PHR with no change in
   conditions. Residuals (`phr_residual_db`) for Round 3: **A +1.59, B +4.05,
   C −5.66 dB** — only Location C is genuinely power-limited once allocation is
   removed. Raw PHR misleads here.
3. **§11 contrast is sharper than stated.** 5G PUSCH `rv0_share` = 1.0000 across
   all 19 units; 4G averages 0.9973. srsenb does send other redundancy versions,
   the 5G stack never does.

## Traps found and now handled in code

- `ul_nof_prbs` / `dl_nof_prbs` are **cumulative over the 1 s reporting period**,
  not the grant width — tens of thousands in a 51-PRB cell. Use
  `ul_prbs_per_tx`.
- 4G writes `t=21 us` **with a space** before the unit; parsed naively that is
  21 seconds, not 21 µs. Cost: uplink decode time out by 10⁶.
- `total_dl_brate= 0.0bps` is space-padded, so it tokenises to an empty value.
- Location B is **6 m**; `Loc2_5m` / "5 m" is a pre-survey nominal label.
- `1 - 28-Jul/**/enb_metrics.csv` is an empty `#eof` stub.
- gNB log timestamps are **UTC**; the CellularLab banner is local (UTC+1). Join
  on the export's `Time:` line.

## Not done

- `control_plane.py` not ported — §8 still reads the old `data/control_plane.csv`.
- Figures not regenerated (no matplotlib in this environment); `figures/*.pdf`
  are still from the old scripts.
- NGAP pcaps confirmed as good appendix material for the core start-up sequence
  (they carry `AMFName: open5gs-amf0`, served GUAMI, relative AMF capacity, and
  an `NGReset` teardown) but **not analysed** — deliberately parked. Note they
  cover the gNB↔AMF association only, not SBI/NRF registration between core NFs;
  `testing_data/logs/` has `amf.log` etc. for that side.
- MAC pcaps still unexploited. Nothing in §1–§11 needs them.

## State of the repo

Everything above is **untracked in git** as of the end of this session.
