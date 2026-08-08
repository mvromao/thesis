# Lab plan — room survey for the methodology floor plan

Short handoff for a Claude instance running at the lab. **The main job this trip is
measurements for a floor-plan diagram, not new radio tests.** Optional extras in §3 only if
time and access allow.

---

## 1. Thirty-second orientation

Marcos is writing an MSc thesis on a private 5G SA network (srsRAN Project gNB + Open5GS,
USRP B210, band n78 at 3410.1 MHz, 20 MHz). Three measurement campaigns are already done and
analysed — `Thesis/analysis/DATA_INVENTORY.md` is the stock-take, and the three
`FINDINGS*.md` files hold the analysis. Nothing about the write-up depends on this trip.

He is drafting the Results chapter himself. The methodology section will include a **plan
view of the lab** showing the radio, the three UE positions, and the obstacles between them —
because the three "distances" are really distance-*plus-obstruction* conditions (2 m line of
sight, 5 m through a partition, ~10 m through a concrete wall) and a table cannot convey that.
Photos already exist; what's missing is dimensions.

Current live gNB config on the RAN host (`gnb_n78.yaml`): `tx_gain 89.75`, **`rx_gain 60`**,
TDD `nof_dl_slots 2 / nof_dl_symbols 5 / nof_ul_slots 2 / nof_ul_symbols 5`.

---

## 2. Primary task — the survey

**Sketch first, measure second.** Draw the room roughly on paper, mark the points, then fill
in numbers. Measuring without a sketch is how you get home and find a missing dimension.

### 2.1 Room

- [ ] Room length × width, and ceiling height
- [ ] Pick **two perpendicular walls** as the origin (call them Wall A and Wall B) and note
      which they are in a photo — every position below is an (A, B) coordinate pair, so the
      plan can be drawn to scale rather than just annotated with distances
- [ ] Doors and windows, position and width, **especially any in a signal path**
- [ ] Anything large and metallic (cabinets, whiteboards, racks, radiators)

### 2.2 Radio

| | Value |
|---|---|
| Distance from Wall A | |
| Distance from Wall B | |
| Antenna height above floor | |
| Antenna orientation / polarisation (vertical? tilted?) | |
| What it sits on (bench, tripod, shelf) | |
| USRP B210 position (if separate from the antenna) | |

- [ ] Photograph the antenna in place, wide enough to show the surroundings
- [ ] Note the **4G rig position too** if the bladeRF setup was somewhere different — the 4G
      baseline is a separate campaign and its geometry matters just as much

### 2.3 The three UE positions

For each of Loc 1 / Loc 2 / Loc 3:

| | Loc 1 | Loc 2 | Loc 3 |
|---|---|---|---|
| Distance from Wall A | | | |
| Distance from Wall B | | | |
| Height above floor | | | |
| **Direct distance to the antenna** (tape or laser) | | | |
| Phone orientation (screen facing where; held or resting) | | | |
| Resting on what (table, hand, shelf) | | | |

- [ ] Photograph each position **from the antenna's viewpoint**, and the antenna from each
      position — that pair makes the obstruction obvious to a reader

### 2.4 Obstacles — the part that matters most

For every obstruction on the antenna→UE path, at each location:

| | What | Material | Thickness | Position along the path |
|---|---|---|---|---|
| Loc 1 | (clear LOS?) | | | |
| Loc 2 | partition | | | |
| Loc 3 | wall | | | |

Material and thickness are the point. Concrete versus plasterboard is a large difference at
3.41 GHz, and it is the reason Loc 2 and Loc 3 are not equivalent conditions. If a wall is
concrete, note whether it's solid or hollow-block if that's visible anywhere.

### 2.5 Honesty note

Record the **method and tolerance** — "tape measure, ±0.05 m" or "paced, ±0.5 m". The thesis
should state it. A schematic plan with an honest tolerance is fine academically; one implying
survey precision that wasn't achieved is not. Do not round numbers into looking exact.

---

## 3. Optional, only if there is time — in priority order

Each is independent. Skip freely; nothing downstream depends on them.

### 3.1 RLC queue resize — ~15 min, highest value

The gNB's DRB downlink RLC AM queue is at the srsRAN default **6.17 MB** and TCP fills it to
99.9 %, inflating latency 35–81× (measured: idle 25–28 ms → 0.5–2.3 s under a download).
The radio itself is capable of a 16 ms floor.

- [ ] In the live config's `qos` → `rlc` → `am` → `tx` block, cut the queue to ~**256 kB**
      (check the exact key spelling for this srsRAN build)
- [ ] **Verify without running a test** — the gNB prints the effective values at DRB setup:
      ```
      rg "DRB1 DL: RLC AM configured" /tmp/gnb.log
      # want: queue_size_bytes ≈ 262144   (was 6172672)
      ```
- [ ] 3 TCP downlink reps at one location, plus a `ping -c 30` **during** one of them
- [ ] Expect: mean RTT 2.66 s → **0.2–0.3 s**, throughput roughly unchanged. If throughput
      drops materially, try 512 kB — the trade-off curve is a better result than either point

This converts "we diagnosed multi-second bufferbloat" into "we diagnosed it, fixed it, and
measured the fix". For a thesis about building and operating a network that is worth a lot.

### 3.2 TDD isolation redo at `rx_gain 70` — ~10 min

The 08-03 isolation run is confounded: it ran at `rx_gain 60`, where the 10 m uplink is
broken, so both arms sat in a degraded regime.

- [ ] Set `rx_gain: 70`, go to Loc 3, uplink only, 3 reps each of:
      - TDD `2 DL : 2 UL` (`nof_dl_slots 2, nof_dl_symbols 5, nof_ul_slots 2, nof_ul_symbols 5`)
      - TDD `3 DL : 1 UL` (`nof_dl_slots 3, nof_dl_symbols 6, nof_ul_slots 1, nof_ul_symbols 2`)
- [ ] **Restore `rx_gain 60` and the 2:2 pattern afterwards** — or record deliberately which
      setting the lab network is being left on, since there is no single correct value
      (that finding is itself a result)

### 3.3 Core NF logs — ~2 min, no radio or UE needed

Only `amf.log` was captured on 08-03. For the walkthrough appendix, grab a cold start of the
rest over SSH:

- [ ] Restart the Open5GS NFs and capture `journalctl -u open5gs-*` for **smf, upf, nrf, udm,
      udr, ausf** alongside amf, from before the restart through a full UE attach

---

## 4. Bring

Tape measure (or laser rangefinder), paper + pen for the sketch, phone for photos, USB drive.
If doing §3: laptop with SSH to the RAN host, and the UE.

---

## 5. Capture conventions if any tests are run

Unchanged from the last two sessions:

- gNB up continuously per location; do **not** restart between reps or when switching
  protocol/direction.
- Keep `metrics: enable_log: true`, `hex_max_size: 0`, `all_level: info`.
- iperf3 server: **distinct logfile path per location** (`--logfile Loc1.json`) —
  `--logfile` appends, it does not truncate. Output is concatenated JSON, not an array.
- Phone exports: `<PROTO>_<DIR><rep>.txt`, or run `scripts/rename_reps.py --apply` after.
- New campaign folder: `Thesis/testing_data/<DD-Mon>/`.

---

## 6. After the trip

1. Copy everything off the USB drive; write the measurements into
   `Thesis/testing_data/PLACEMENT.md` (dimensions, coordinates, materials, tolerance, photo
   filenames).
2. If §3.1 or §3.2 ran, the analysis pipeline is in `Thesis/analysis/scripts/` — the
   `parse_0803_*.py` set is the current generation; update the campaign path at the top.
3. Write a `SESSION_LOG_<date>.md` recording what was actually changed on the RAN host and
   what was left running, following the existing session logs' structure.
