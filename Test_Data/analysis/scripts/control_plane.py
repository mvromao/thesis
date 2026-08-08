"""Extract control-plane procedure timings from the 24 srsRAN traces.

Reads only the signalling lines (RRC / NGAP / S1AP / PHY-PRACH), which live in
the first few % of each file, and reconstructs the attach / registration
procedure with millisecond timings.
"""
import re
import csv
from datetime import datetime
from pathlib import Path

ROOT = Path(r"d:/Documents/Thesis/thesis/Thesis/testing_data")
OUT = Path(r"C:/Users/renedito/AppData/Local/Temp/claude/d--Documents-Thesis-thesis/b1332cd8-faa5-4c44-98cf-08890c96dfe4/scratchpad")

TS = re.compile(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+)\s+\[([A-Z0-9\-]+)\s*\]\s+\[[IWED]\]\s*(.*)$")

# marker name -> regex on the message body
MARK_5G = {
    "ng_setup_req":  r"Tx PDU: NGSetupRequest",
    "ng_setup_rsp":  r"Rx PDU: NGSetupResponse",
    "prach":         r"PRACH: rsi=",
    "rrc_setup_req": r"CCCH UL rrcSetupRequest",
    "rrc_setup":     r"CCCH DL rrcSetup$",
    "rrc_setup_cpl": r"DCCH UL rrcSetupComplete",
    "initial_ue":    r"InitialUEMessage",
    "sec_cmd":       r"DCCH DL securityModeCommand",
    "sec_cpl":       r"DCCH UL securityModeComplete",
    "ics_req":       r"InitialContextSetupRequest",
    "ics_rsp":       r"InitialContextSetupResponse",
    "pdu_sess_req":  r"PDUSessionResourceSetupRequest",
    "pdu_sess_rsp":  r"PDUSessionResourceSetupResponse",
    "rrc_reconf":    r"DCCH DL rrcReconfiguration",
    "rrc_reconf_c":  r"DCCH UL rrcReconfigurationComplete",
}
MARK_4G = {
    "ng_setup_req":  r"Tx S1AP SDU, s1SetupRequest",
    "ng_setup_rsp":  r"Rx S1AP SDU - S1SetupResponse",
    "prach":         r"PRACH: cc=",
    "rrc_setup_req": r"rrcConnectionRequest",
    "rrc_setup":     r"rrcConnectionSetup \(",
    "rrc_setup_cpl": r"rrcConnectionSetupComplete",
    "initial_ue":    r"Tx S1AP SDU, InitialUEMessage",
    "sec_cmd":       r"securityModeCommand",
    "sec_cpl":       r"securityModeComplete",
    "ics_req":       r"Rx S1AP SDU - InitialContextSetupRequest",
    "ics_rsp":       r"Tx S1AP SDU, InitialContextSetupResponse",
    "pdu_sess_req":  r"Rx S1AP SDU - InitialContextSetupRequest",   # E-RAB rides in ICS
    "pdu_sess_rsp":  r"Tx S1AP SDU, InitialContextSetupResponse",
    "rrc_reconf":    r"rrcConnectionReconfiguration \(",
    "rrc_reconf_c":  r"rrcConnectionReconfigurationComplete",
}
NAS_UL = {"5G": r"UplinkNASTransport", "4G": r"Tx S1AP SDU, UplinkNASTransport"}
NAS_DL = {"5G": r"DownlinkNASTransport", "4G": r"Rx S1AP SDU - DownlinkNASTransport"}


def parse_ts(s):
    return datetime.strptime(s[:26], "%Y-%m-%dT%H:%M:%S.%f")


def ms(a, b):
    if a is None or b is None:
        return None
    return round((b - a).total_seconds() * 1000, 2)


rows = []
for folder in sorted(p.parent for p in ROOT.glob("*/*/*/*/trace.log")):
    tech, loc, protocol, direction = folder.parts[-4:]
    log = next((folder / f for f in ("gnb.log", "enb.log") if (folder / f).exists()), None)
    if not log:
        continue
    marks = MARK_5G if tech == "5G" else MARK_4G
    rx = {k: re.compile(v) for k, v in marks.items()}
    rx_nas_ul = re.compile(NAS_UL[tech])
    rx_nas_dl = re.compile(NAS_DL[tech])

    first = {}
    nas_ul = nas_dl = 0
    n_prach = 0
    ue_ctx_release = 0
    stop_after_first_session = False

    with open(log, encoding="utf-8", errors="ignore") as f:
        for line in f:
            m = TS.match(line)
            if not m:
                continue
            ts_s, layer, msg = m.groups()
            if layer.strip() not in ("RRC", "NGAP", "S1AP", "PHY", "PHY0", "PHY1",
                                     "PHY2", "CU-CP", "DU-MNG", "MAC"):
                continue
            t = parse_ts(ts_s)
            for name, r in rx.items():
                if r.search(msg):
                    n_prach += (name == "prach")
                    first.setdefault(name, t)
            if rx_nas_ul.search(msg):
                nas_ul += 1
            if rx_nas_dl.search(msg):
                nas_dl += 1
            if "UEContextRelease" in msg or "Releasing UE" in msg:
                ue_ctx_release += 1
            if "pdu_sess_rsp" in first and (t - first["pdu_sess_rsp"]).total_seconds() > 5:
                stop_after_first_session = True
            if stop_after_first_session and n_prach >= 1:
                break

    g = first.get
    rows.append({
        "tech": tech, "location": loc, "protocol": protocol, "direction": direction,
        "ng_s1_setup_ms":        ms(g("ng_setup_req"), g("ng_setup_rsp")),
        "rrc_setup_ms":          ms(g("rrc_setup_req"), g("rrc_setup_cpl")),
        "rrc_req_to_setup_ms":   ms(g("rrc_setup_req"), g("rrc_setup")),
        "auth_nas_ms":           ms(g("initial_ue"), g("ics_req")),
        "security_ms":           ms(g("sec_cmd"), g("sec_cpl")),
        "ics_ms":                ms(g("ics_req"), g("ics_rsp")),
        "reconf_ms":             ms(g("rrc_reconf"), g("rrc_reconf_c")),
        "pdu_session_ms":        ms(g("pdu_sess_req"), g("pdu_sess_rsp")),
        "total_attach_ms":       ms(g("rrc_setup_req"), g("pdu_sess_rsp")),
        "prach_to_session_ms":   ms(g("prach"), g("pdu_sess_rsp")),
        "n_prach": n_prach, "n_nas_ul": nas_ul, "n_nas_dl": nas_dl,
        "n_ue_ctx_release": ue_ctx_release,
    })

fields = list(rows[0].keys())
with open(OUT / "control_plane.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(rows)

# pretty print
hdr = ["tech", "location", "protocol", "direction", "ng_s1_setup_ms", "rrc_setup_ms",
       "auth_nas_ms", "security_ms", "ics_ms", "reconf_ms", "pdu_session_ms",
       "total_attach_ms", "prach_to_session_ms", "n_prach"]
print(" | ".join(f"{h:>18s}" if i > 3 else f"{h:<10s}" for i, h in enumerate(hdr)))
for r in rows:
    print(" | ".join(
        (f"{str(r[h]):>18s}" if i > 3 else f"{str(r[h]):<10s}") for i, h in enumerate(hdr)))
print("\nwrote control_plane.csv")
