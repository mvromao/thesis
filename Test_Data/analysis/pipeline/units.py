"""Value parsing for srsRAN log fields.

srsRAN writes numbers with SI multipliers and unit suffixes mixed together
(`56.9kbps`, `4ms`, `132ns`, `10%`, `-0.6`), and uses three distinct sentinels
for "no value": `n/a`, `inf`/`nan`, and `ovl`.

`ovl` is *not* missing data -- it means the receiver front end was saturated and
the RSRP estimate is invalid. That distinction is the whole basis of the
rx_gain 70 overload finding, so it is surfaced separately rather than folded
into None by callers that care (see `is_overload`).

Consolidated from scripts/parse_0803_metrics.py `val()` and scripts/scan_phy.py
`val()`, which had drifted apart: the first handled SI+time units but not
bracketed ranges, the second handled ranges but not time units.
"""
import re

_SI = {"k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9, "m": 1e-3, "u": 1e-6, "n": 1e-9}
# srsRAN mixes the short and long spellings in the same line
# (`t=89.3us` on PHY, `slot_duration=500usec` on MAC cell).
_TIME = {"ns": 1e-9, "nsec": 1e-9, "us": 1e-6, "usec": 1e-6,
         "ms": 1e-3, "msec": 1e-3, "s": 1.0, "sec": 1.0}

# 56.9kbps | -0.6 | 10% | 132ns | 7.79ms | 500usec | 3.91k | 1.0
# The suffix is captured whole and interpreted afterwards. Splitting it into
# (SI prefix)(unit) inside the regex does not work: the prefix class would eat
# the `u` of `usec` and the `m` of `ms`, silently returning microseconds and
# milliseconds as if they were seconds.
_NUM = re.compile(r"^(-?\d+\.?\d*)\s*([A-Za-z%]*)$")
# "[26-43)" or "(2-13)" -> width.  Ranges are pre-collapsed by SPACED below.
_RANGE = re.compile(r"^[\[(](\d+)-(\d+)[)\]]$")
# srsRAN writes slot ranges as "[26, 29)"; collapse the space so the whole
# token survives a whitespace split.
SPACED = re.compile(r"([\[(])(\d+),\s*(\d+)([)\]])")
# leading number of an otherwise unparseable token, e.g. "11.8dB" -> 11.8
_LEAD = re.compile(r"^(-?\d+\.?\d*)")

SENTINELS = frozenset({"n/a", "inf", "-inf", "nan", "ovl", "", "-"})


def is_overload(s):
    """True when srsRAN reported receiver saturation rather than a measurement."""
    return isinstance(s, str) and s.strip() == "ovl"


# srsRAN 4G separates a value from its unit with a space (`t=21 us`,
# `snr=21.5 dB`, `ta=0.4 us`) where srsRAN 5G does not (`t=89.3us`).
# Left unjoined, `t=21 us` parses as a bare 21 -- read as 21 *seconds* by a
# caller expecting base units, which turned a 21 us decode into 21 s.
_SPACED_UNIT = re.compile(r"(\d)[ \t]+(dBfs|dBm|dB|usec|msec|nsec|us|ms|ns|hz|Hz)\b")


def join_spaced_units(text):
    """`t=21 us` -> `t=21us`, so one field stays one token."""
    return _SPACED_UNIT.sub(r"\1\2", text)


def collapse_ranges(text):
    """`slots=[45.3, 100.0)` -> `slots=[45.3-100.0)` so tokens stay whitespace-safe."""
    return SPACED.sub(r"\1\2-\3\4", text)


def val(s, unit_scale=True):
    """Parse one srsRAN field value to float, or None if it carries no number.

    unit_scale=True converts to base SI units (bits/s, seconds, fraction for %).
    unit_scale=False keeps the printed magnitude, which is what you want when
    the column name already states the unit (e.g. `dl_brate_Mbps`).
    """
    if s is None:
        return None
    s = s.strip().strip("{}")
    if s in SENTINELS:
        return None

    m = _RANGE.match(s)
    if m:  # a range is reported as its width
        return float(int(m.group(2)) - int(m.group(1)))

    m = _NUM.match(s)
    if m:
        num, suffix = m.groups()
        v = float(num)
        if not unit_scale or not suffix:
            return v
        if suffix in _TIME:                       # 132ns, 500usec, 4ms
            return v * _TIME[suffix]
        if suffix == "%":                         # 10% -> 0.10
            return v / 100.0
        if suffix.endswith("bps"):                # 56.9kbps -> 56900
            return v * _SI.get(suffix[:-3], 1.0)
        if suffix in _SI:                         # 3.91k -> 3910
            return v * _SI[suffix]
        return v                                  # 11.8dB, 14 -> magnitude as printed

    m = _LEAD.match(s)
    return float(m.group(1)) if m else None


def kv_pairs(body, keys=None):
    """Tokenise a `k=v k=v` log body into a dict of raw strings.

    Tolerant by design: srsRAN adds and removes fields per slot depending on
    what was multiplexed (the optional `ack=` on PUSCH, `srs_ta=` only when SRS
    is configured), so a rigid field-order regex breaks on perfectly good lines.
    Reasoning inherited from scripts/scan_phy.py.
    """
    out = {}
    for tok in collapse_ranges(join_spaced_units(body)).split():
        if "=" not in tok:
            continue
        k, _, v = tok.partition("=")
        if keys is None or k in keys:
            out[k] = v.rstrip(",;")
    return out


# srsRAN 4G reports modulation as bits per symbol, 5G by name. Canonicalise so
# the two stacks' modulation ladders can be compared at all.
_MOD_ORDER = {"2": "QPSK", "4": "16QAM", "6": "64QAM", "8": "256QAM"}


def mod_name(raw):
    if raw is None:
        return None
    s = str(raw).strip("{}").strip()
    return _MOD_ORDER.get(s, s.upper() if s else None)


# `name=[ ... ]` -- three different things hide behind this one syntax:
#   wall_clock_latency=[avg=24usec max=3334usec max_slot=45.5]   nested k=v
#   pusch_rbs_per_tdd_slot_idx=[0, 0, 0, 0, 0]                   numeric array
#   slots=[45.3, 100.0)                                          half-open range
# A plain whitespace split silently mangles the first (the inner `max=` and
# `max_slot=` keys collide across groups) and the second (splits one field into
# five tokens). They must be lifted out before tokenising the remainder.
_GROUP = re.compile(r"(\w+)=\[([^\]\)]*)\]")
_RANGE_FIELD = re.compile(r"(\w+)=[\[(]([^\]\)]*)[\)\]]")
_PAD = re.compile(r"=[ \t]+(?=[-\d])")


def parse_metrics_body(body):
    """Flatten one `[METRICS ]` line body into {name: raw string}.

    Nested groups are flattened with an underscore
    (`wall_clock_latency=[avg=24usec ...]` -> `wall_clock_latency_avg`), numeric
    arrays are joined with `|` and kept whole (`0|0|0|0|0`) so the per-slot
    structure survives into the CSV, and ranges collapse to their width.
    """
    out = {}
    # srsRAN right-aligns numbers in a fixed-width field, so a value can be
    # preceded by padding: `total_dl_brate= 0.0bps`. Without this the two cell
    # throughput fields tokenise to empty strings.
    rest = _PAD.sub("=", body)

    def _take_group(m):
        name, inner = m.group(1), m.group(2).strip()
        if "=" in inner:
            for tok in inner.split():
                if "=" in tok:
                    k, _, v = tok.partition("=")
                    out[f"{name}_{k}"] = v
        else:
            out[name] = "|".join(x.strip() for x in inner.split(",")) if inner else ""
        return " "

    rest = _GROUP.sub(_take_group, rest)

    def _take_range(m):
        name, inner = m.group(1), m.group(2)
        out[name] = "|".join(x.strip() for x in inner.split(","))
        return " "

    rest = _RANGE_FIELD.sub(_take_range, rest)

    for tok in rest.split():
        if "=" in tok:
            k, _, v = tok.partition("=")
            out.setdefault(k, v.rstrip(","))
    return out


def array_vals(s):
    """`'0|12|0|9|0'` -> [0.0, 12.0, 0.0, 9.0, 0.0]; None-safe."""
    if not s:
        return []
    return [val(x) for x in str(s).split("|")]
