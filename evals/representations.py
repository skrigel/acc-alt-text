"""
Builds chart representations A, B, C from VisText examples.

A: raw scenegraph text field (as-is from VisText JSON)
B: normalized ChartRepresentation schema serialized as JSON
C: repr B + L1 facts pre-filled; model generates only L2/L3 prose
"""
import json
import re
from typing import Optional


# ── repr A ────────────────────────────────────────────────────────────────────

def repr_a(example: dict) -> str:
    """Return the raw VisText scenegraph text field."""
    return str(example["scenegraph"])


# ── datatable parser (for repr B) ─────────────────────────────────────────────

def _parse_datatable(example: dict) -> list[dict]:
    """
    Parse the VisText datatable field into a list of {x, y} dicts.

    Datatable format:
      {title} <s> {x_label} {y_label} {data...}

    Bar:  data is alternating  value  label-words  (float first)
    Area/Line: data is alternating  x-label  value  (text/date first, float last)
    """
    raw = str(example.get("datatable", ""))
    parts = raw.split("<s>", 1)
    if len(parts) < 2:
        return []
    data_str = parts[1].strip()

    x_label = example["L1_properties"][2]
    y_label = example["L1_properties"][3]
    chart_type = example["L1_properties"][0]

    # Strip x_label and y_label from the head of data_str (they appear verbatim)
    for label in (x_label, y_label):
        if data_str.startswith(label):
            data_str = data_str[len(label):].strip()

    data_str = data_str.strip()

    if chart_type == "bar":
        return _parse_bar(data_str)
    else:
        return _parse_area_line(data_str)


def _parse_bar(data_str: str) -> list[dict]:
    """
    Bar datatable: float value THEN text label per entry.
    Example: '3.9 Miami, FL 3.12 Salt Lake City, UT 2.98 Los Angeles, CA'
    """
    number_re = re.compile(r'\b\d[\d,]*\.?\d*\b')
    matches = list(number_re.finditer(data_str))
    result = []
    for i, m in enumerate(matches):
        try:
            val = float(m.group().replace(",", ""))
        except ValueError:
            continue
        label_start = m.end()
        label_end = matches[i + 1].start() if i + 1 < len(matches) else len(data_str)
        label = data_str[label_start:label_end].strip().strip(",").strip()
        if label:
            result.append({"x": label, "y": val})
    return result


def _parse_area_line(data_str: str) -> list[dict]:
    """
    Area/line datatable: text label (possibly a date) THEN numeric value per entry.

    Handles two patterns:
      'Dec 31, 2005 123975 Dec 31, 2006 121356'  (date label)
      '2006 37.22 2007 43.21'                     (year label)
    """
    # Try date-based pattern first: 'Mon DD, YYYY value'
    date_pattern = re.compile(
        r'([A-Za-z][a-z]{2}\.?\s+\d{1,2},?\s+\d{4})\s+([\d,.]+)'
    )
    matches = date_pattern.findall(data_str)
    if matches:
        return [{"x": m[0].strip(), "y": float(m[1].replace(",", ""))} for m in matches]

    # Year-based pattern: 'YYYY value'
    year_pattern = re.compile(r'\b(\d{4})\s+([\d,.]+)\b')
    matches = year_pattern.findall(data_str)
    if matches:
        return [{"x": m[0], "y": float(m[1].replace(",", ""))} for m in matches]

    # Generic fallback: alternate number / text
    tokens = data_str.split()
    result, i = [], 0
    while i < len(tokens) - 1:
        label_parts = []
        while i < len(tokens) and not re.fullmatch(r'[\d,.]+', tokens[i]):
            label_parts.append(tokens[i])
            i += 1
        if i < len(tokens):
            try:
                val = float(tokens[i].replace(",", ""))
                if label_parts:
                    result.append({"x": " ".join(label_parts), "y": val})
                i += 1
            except ValueError:
                i += 1
    return result


# ── scenegraph tick extractor (for repr B) ────────────────────────────────────

def _extract_ticks(scenegraph_text: str) -> tuple[list[str], list[str]]:
    """Parse xtick and ytick values from the VisText scenegraph text."""
    xtick_m = re.search(r'xtick\s+(.*?)(?=\s+ytick|\s+marks|$)', scenegraph_text)
    ytick_m = re.search(r'ytick\s+(.*?)(?=\s+marks|$)', scenegraph_text)

    def parse_vals(tick_str: str) -> list[str]:
        return re.findall(r'val\s+(\S+(?:\s+\S+)*?)(?=\s+[xy]\s+\d|\s*$)', tick_str)

    x_ticks = parse_vals(xtick_m.group(1)) if xtick_m else []
    y_ticks = parse_vals(ytick_m.group(1)) if ytick_m else []
    return x_ticks, y_ticks


# ── repr B ────────────────────────────────────────────────────────────────────

def repr_b(example: dict) -> str:
    """
    Normalized ChartRepresentation schema serialized as JSON.
    Uses L1_properties for structural metadata, scenegraph for tick values,
    and datatable for data points.
    """
    props = example["L1_properties"]
    chart_type, title, x_label, y_label, x_scale, y_scale = props

    x_ticks, y_ticks = _extract_ticks(str(example["scenegraph"]))
    data_points = _parse_datatable(example)

    schema = {
        "chart_type": chart_type,
        "title": title,
        "x_axis": {
            "label": x_label,
            "scale": x_scale,
            "tick_values": x_ticks,
        },
        "y_axis": {
            "label": y_label,
            "scale": y_scale,
            "tick_values": y_ticks,
        },
        "data_points": data_points,
    }
    return json.dumps(schema, indent=2)


# ── repr C ────────────────────────────────────────────────────────────────────

def build_l1_sentence(example: dict) -> str:
    """Deterministically produce the L1 sentence from L1_properties."""
    props = example["L1_properties"]
    chart_type, title, x_label, y_label, x_scale, y_scale = props
    return (
        f'This is a {chart_type} chart titled "{title}". '
        f'The x-axis shows {x_label} ({x_scale}). '
        f'The y-axis shows {y_label} ({y_scale}).'
    )


def repr_c(example: dict) -> str:
    """
    Schema JSON + L1 facts pre-filled.
    The prompt using this repr should ask the model to generate ONLY L2/L3 prose;
    L1 is concatenated deterministically.
    """
    props = example["L1_properties"]
    chart_type, title, x_label, y_label, x_scale, y_scale = props
    x_ticks, y_ticks = _extract_ticks(str(example["scenegraph"]))
    data_points = _parse_datatable(example)

    given_facts = {
        "chart_type": chart_type,
        "title": title,
        "x_axis_label": x_label,
        "x_axis_scale": x_scale,
        "y_axis_label": y_label,
        "y_axis_scale": y_scale,
    }
    chart_data = {
        "x_tick_values": x_ticks,
        "y_tick_values": y_ticks,
        "data_points": data_points,
    }
    schema = {
        "given_l1_facts": given_facts,
        "chart_data": chart_data,
    }
    return json.dumps(schema, indent=2)


# ── dispatch ──────────────────────────────────────────────────────────────────

REPR_BUILDERS = {
    "A": repr_a,
    "B": repr_b,
    "C": repr_c,
}


def build_repr(example: dict, repr_key: str) -> str:
    return REPR_BUILDERS[repr_key](example)