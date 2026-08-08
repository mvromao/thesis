#!/usr/bin/env python3
"""Fix two librsvg pattern-rendering bugs that make Inkscape hatch fills vanish.

1. Href-chained pattern instances. Applying a stock hatch/pattern swatch in Inkscape
   creates an empty <pattern> carrying only a position/transform override, linked to the
   real content via xlink:href="#other-pattern". librsvg (used by rsvg-convert) doesn't
   reliably resolve that href-inheritance, so the hatch silently renders as nothing. Fixed
   by rewriting each instance as a fully self-contained <pattern> (merging in
   patternUnits/width/height/style and the referenced pattern's child content).

2. Oversized patternTransform translate values. Inkscape sometimes emits huge translate
   components in a pattern's patternTransform (matrix(...,e,f) or translate(x,y)) -- values
   in the tens of thousands are common after repeated moves/transforms in the editor.
   librsvg fails to render the pattern at all when this happens (confirmed by isolated
   testing, independent of bug #1). Since patterns tile periodically, reducing an oversized
   translate component modulo a small bound is visually equivalent -- fixed by doing that
   reduction wherever a translate component exceeds a threshold.

Everything else in the file is left byte-for-byte identical.

Usage: flatten_svg_patterns.py input.svg output.svg
"""
import re
import sys
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_NS = "{http://www.w3.org/1999/xlink}"

# Empirically, translate components around 3x10^4 make librsvg fail to render the pattern
# at all. Reduce anything past this threshold modulo REDUCE_MODULUS -- patterns tile
# periodically, so this doesn't change the drawing, just avoids whatever numerical issue
# librsvg hits at large magnitudes.
TRANSLATE_THRESHOLD = 1000
REDUCE_MODULUS = 1000


def _reduce(value_str: str) -> str:
    v = float(value_str)
    if abs(v) > TRANSLATE_THRESHOLD:
        v = v % REDUCE_MODULUS
    # keep integers looking like integers
    return str(int(v)) if v == int(v) else repr(v)


def fix_oversized_translates(svg_text: str) -> str:
    def fix_transform(m: "re.Match") -> str:
        kind, args = m.group(1), m.group(2)
        parts = [p.strip() for p in re.split(r"[,\s]+", args.strip()) if p.strip()]
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            return m.group(0)
        if kind == "matrix" and len(nums) == 6:
            nums[4] = float(_reduce(str(nums[4])))
            nums[5] = float(_reduce(str(nums[5])))
        elif kind == "translate" and len(nums) >= 1:
            nums[0] = float(_reduce(str(nums[0])))
            if len(nums) >= 2:
                nums[1] = float(_reduce(str(nums[1])))
        else:
            return m.group(0)
        new_args = ",".join(_reduce(str(n)) if i in (4, 5) or kind == "translate" else str(n) for i, n in enumerate(nums))
        return f"{kind}({new_args})"

    def fix_pattern_transform_attr(m: "re.Match") -> str:
        value = m.group(1)
        new_value = re.sub(r"(matrix|translate)\(([^)]*)\)", fix_transform, value)
        if new_value != value:
            print(f"Reduced oversized translate in patternTransform: {value!r} -> {new_value!r}", file=sys.stderr)
        return f'patternTransform="{new_value}"'

    return re.sub(r'patternTransform="([^"]*)"', fix_pattern_transform_attr, svg_text)


def flatten(svg_text: str) -> str:
    root = ET.fromstring(svg_text)
    patterns_by_id = {}
    instance_ids = []  # (id, href_target), in document order

    for pat in root.iter(f"{SVG_NS}pattern"):
        pid = pat.get("id")
        href = pat.get(f"{XLINK_NS}href")
        patterns_by_id[pid] = pat
        if href and len(list(pat)) == 0:
            instance_ids.append((pid, href.lstrip("#")))

    out = svg_text
    for inst_id, base_id in instance_ids:
        base = patterns_by_id.get(base_id)
        if base is None:
            print(f"!! warning: {inst_id} references undefined pattern #{base_id}, skipping", file=sys.stderr)
            continue

        # Exact source text of the empty self-closing instance tag, e.g. <pattern ... />
        inst_match = re.search(
            r'<pattern\b[^>]*\bid="%s"[^>]*/>' % re.escape(inst_id), out
        )
        if not inst_match:
            print(f"!! warning: could not locate self-closing tag for {inst_id}, skipping", file=sys.stderr)
            continue

        # Exact source text of the base pattern's opening tag's attributes and its children
        base_match = re.search(
            r'<pattern\b([^>]*\bid="%s"[^>]*)>(.*?)</pattern>' % re.escape(base_id),
            out, re.DOTALL,
        )
        if not base_match:
            print(f"!! warning: could not locate full definition for base pattern {base_id}, skipping", file=sys.stderr)
            continue
        base_attrs_text, base_children_text = base_match.groups()

        # Pull inheritable attributes (patternUnits, width, height, style) from the base tag
        inheritable = {}
        for attr in ("patternUnits", "width", "height", "style"):
            m = re.search(r'%s="([^"]*)"' % attr, base_attrs_text)
            if m:
                inheritable[attr] = m.group(1)

        inst_tag_text = inst_match.group(0)
        # Drop the xlink:href attribute -- no longer needed once flattened
        new_open = re.sub(r'\s*xlink:href="[^"]*"', "", inst_tag_text)
        # Insert the inherited attributes right after the opening "<pattern"
        insert_at = new_open.index("<pattern") + len("<pattern")
        attrs_str = "".join(f' {k}="{v}"' for k, v in inheritable.items())
        new_open = new_open[:insert_at] + attrs_str + new_open[insert_at:]
        # Turn the self-closing tag into an opening tag with the base's children inline
        new_open = new_open[:-2] + ">"  # strip the trailing "/>"
        replacement = f"{new_open}{base_children_text}</pattern>"

        out = out.replace(inst_tag_text, replacement, 1)
        print(f"Flattened: {inst_id} (was href=#{base_id}) -- inherited {list(inheritable)}", file=sys.stderr)

    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    src_path, out_path = sys.argv[1], sys.argv[2]
    with open(src_path, encoding="utf-8") as f:
        text = f.read()
    result = flatten(text)
    result = fix_oversized_translates(result)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result)
