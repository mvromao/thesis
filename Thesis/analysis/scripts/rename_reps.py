"""Rename the Loc2/Loc3 CellularLab exports to Loc1's <PROTO>_<DIR><rep>.txt scheme.

Condition comes from the iperf3 command line inside each file; rep number from
start-time order within that condition. Writes a rename_manifest.csv per folder
so the original CellularLab filenames are never lost.

Run with --apply to actually rename; default is a dry run.
"""
import re
import sys
import csv
from pathlib import Path

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data/5G_new_methodology")
APPLY = "--apply" in sys.argv

for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
    files = sorted(folder.glob("iPerf3_*.txt"))
    if not files:
        print(f"{folder.name}: already named (or nothing to do)")
        continue

    entries = []
    for f in files:
        txt = f.read_text(encoding="utf-8", errors="ignore")
        cmd = next((l for l in txt.splitlines() if l.strip().startswith("iperf3 -c")), "")
        proto = "UDP" if " -u" in cmd else "TCP"
        direction = "DL" if " -R" in cmd else "UL"
        m = re.search(r"iPerf3_(\d{8})_(\d{6})_", f.name)
        stamp = m.group(1) + m.group(2)
        entries.append({"path": f, "proto": proto, "dir": direction, "stamp": stamp})

    entries.sort(key=lambda e: (e["proto"], e["dir"], e["stamp"]))
    counter = {}
    for e in entries:
        k = (e["proto"], e["dir"])
        counter[k] = counter.get(k, 0) + 1
        e["rep"] = counter[k]
        e["new"] = f"{e['proto']}_{e['dir']}{e['rep']}.txt"

    entries.sort(key=lambda e: e["stamp"])
    print(f"\n=== {folder.name} — {len(entries)} files ===")
    clash = [e for e in entries if (folder / e["new"]).exists()
             and (folder / e["new"]) != e["path"]]
    if clash:
        print("  ABORT: target names already exist:", [e["new"] for e in clash])
        continue
    for e in entries:
        print(f"  {e['path'].name:42s} -> {e['new']}")

    if APPLY:
        manifest = folder / "rename_manifest.csv"
        with open(manifest, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["original_filename", "new_filename", "protocol",
                        "direction", "rep", "local_start_time"])
            for e in entries:
                s = e["stamp"]
                w.writerow([e["path"].name, e["new"], e["proto"], e["dir"], e["rep"],
                            f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}:{s[12:14]}"])
        for e in entries:
            e["path"].rename(folder / e["new"])
        print(f"  renamed {len(entries)} files; manifest -> {manifest.name}")

if not APPLY:
    print("\n(dry run — re-run with --apply to rename)")
