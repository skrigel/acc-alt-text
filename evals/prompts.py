"""
P1 / P2 / P3 prompt templates for the zero-shot sweep.

Each template takes a `repr_text` (string) and, for repr C, also a
`l1_sentence` (the deterministically generated L1 line).

All prompts ask for a SHORT / LONG split so the same parse_output() works
across all cells.
"""

from evals.representations import build_l1_sentence

# ── worked examples (shared across P2/P3) ─────────────────────────────────────

_P2_EXAMPLE = """\
Example:
SHORT: Bar chart titled "Top Programming Languages 2024" with x-axis showing \
Share (%) from 0 to 35% and y-axis listing programming languages.
LONG: Python leads with 29.9%, roughly double Java's 13.3% in second place. \
JavaScript ranks third at 12.1%, and there is a steep drop-off after the \
top two, suggesting Python's dominance is a clear outlier."""

_P3_EXAMPLE = """\
Example chart: bar chart, title "Top Programming Languages 2024", \
x-axis Share (%) 0–35%, y-axis language (categorical).

SHORT: Bar chart titled "Top Programming Languages 2024" with x-axis showing \
Share (%) from 0 to 35% and y-axis listing programming languages.

LONG: [L2] Python leads with 29.9%, more than double Java's 13.3% in \
second place. JavaScript ranks third at 12.1%. The top three languages \
account for over half of all measured share. [L3] The distribution has a \
pronounced right-skewed shape with a steep drop-off after the first two \
bars. Python's lead is anomalous — roughly 2.3× the third-place language — \
suggesting market concentration at the top."""


# ── P1: minimal ───────────────────────────────────────────────────────────────

def p1(repr_text: str, l1_sentence: str = "") -> str:
    return f"Generate alt-text for this chart:\n\n{repr_text}"


# ── P2: WAI-grounded ──────────────────────────────────────────────────────────

def p2(repr_text: str, l1_sentence: str = "") -> str:
    return f"""\
You are writing alt-text for a data visualization intended for blind or \
low-vision users.

Per WAI-ARIA guidelines, chart alt-text has two parts:
1. SHORT (one sentence, for the alt attribute): chart type, title, both \
axis labels with units and ranges.
2. LONG (detailed paragraph, for aria-describedby): key statistical \
patterns — extrema, trends, comparisons — plus any salient visual \
structure or anomalies.

{_P2_EXAMPLE}

Now generate alt-text for this chart:

{repr_text}

Respond in exactly this format:
SHORT: <one sentence>
LONG: <detailed paragraph>"""


# ── P3: rubric-grounded ───────────────────────────────────────────────────────

def p3(repr_text: str, l1_sentence: str = "") -> str:
    return f"""\
You are writing accessible alt-text for a data visualization, structured \
into three levels of detail.

L1 (put in SHORT): structural facts only
- Chart type (specific: "bar chart", "line graph", "area chart")
- Full title
- Both axis labels with units
- Both axis ranges

L2 (put in LONG): statistical patterns
- Extrema or start/end values with approximate quantities
- Net change or rank ordering
- At least one direct point-wise comparison

L3 (put in LONG): perceptual insights
- Overall shape or pattern described in natural language appropriate to \
the chart type
- Any salient anomaly or exception: name it, locate it approximately, \
contrast it to the overall pattern

{_P3_EXAMPLE}

Now generate alt-text for this chart:

{repr_text}

Respond in exactly this format:
SHORT: <one sentence covering L1>
LONG: <paragraph covering L2 and L3>"""


# ── repr-C variants: model generates LONG only; SHORT is pre-filled ───────────

def p1_c(repr_text: str, l1_sentence: str) -> str:
    return f"""\
The following L1 structural facts have been extracted from the chart:

{repr_text}

Using only the data above, write a LONG description covering:
- Key statistical values, extrema, and at least one comparison (L2)
- Overall trend or shape, and any salient anomaly (L3)

Respond in exactly this format:
SHORT: {l1_sentence}
LONG: <your description>"""


def p2_c(repr_text: str, l1_sentence: str) -> str:
    return f"""\
You are writing the long description (aria-describedby) for a data \
visualization. The short description (alt attribute) has already been \
generated and is shown below — do not reproduce it.

Per WAI-ARIA guidelines, the long description should cover:
- Key statistical patterns: extrema, trends, comparisons (L2)
- Overall visual structure and any notable anomaly (L3)

{_P2_EXAMPLE}

Chart data:
{repr_text}

Respond in exactly this format:
SHORT: {l1_sentence}
LONG: <your long description>"""


def p3_c(repr_text: str, l1_sentence: str) -> str:
    return f"""\
You are writing the long description (aria-describedby) for a data \
visualization. The L1 structural summary is already provided — do not \
regenerate it.

Your LONG description must cover all of the following:

L2 — statistical patterns:
- Extrema or start/end values with approximate quantities
- Net change or rank ordering
- At least one direct point-wise comparison

L3 — perceptual insights:
- Overall shape or pattern described naturally
- Any salient anomaly: name it, locate it approximately, and contrast it \
to the overall trend

{_P3_EXAMPLE}

Chart data:
{repr_text}

Respond in exactly this format:
SHORT: {l1_sentence}
LONG: <your L2 + L3 description>"""


# ── dispatch ──────────────────────────────────────────────────────────────────

# Keyed by (prompt_key, repr_key) — repr C has its own prompt variants.
_PROMPT_FNS = {
    ("P1", "A"): p1,
    ("P1", "B"): p1,
    ("P1", "C"): p1_c,
    ("P2", "A"): p2,
    ("P2", "B"): p2,
    ("P2", "C"): p2_c,
    ("P3", "A"): p3,
    ("P3", "B"): p3,
    ("P3", "C"): p3_c,
}


def build_prompt(example: dict, repr_text: str, prompt_key: str, repr_key: str) -> str:
    fn = _PROMPT_FNS[(prompt_key, repr_key)]
    l1 = build_l1_sentence(example) if repr_key == "C" else ""
    return fn(repr_text, l1)


import re


def parse_output(text: str) -> tuple[str, str]:
    """Split model output into (short, long). Returns ('', '') on parse failure."""
    short_m = re.search(r'SHORT:\s*(.*?)(?=\nLONG:|$)', text, re.DOTALL | re.IGNORECASE)
    long_m  = re.search(r'LONG:\s*(.*?)$',             text, re.DOTALL | re.IGNORECASE)
    short = short_m.group(1).strip() if short_m else ""
    long  = long_m.group(1).strip()  if long_m  else ""
    return short, long
