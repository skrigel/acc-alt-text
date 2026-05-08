"""
LLM judges for L2/L3 scoring.

Default judge model: Qwen/Qwen2.5-7B-Instruct via Hugging Face Router.
Optional Claude judge model: claude-sonnet-4-6 via Anthropic API.
Scores are kept separate from the programmatic L1 scorer in l1_eval.py.

Score fields returned:
  L2:
    statistical_relational_completeness  0-2
    statistical_relational_precision     0-2
  L3:
    perceptual_cognitive_identification  0-2
    exception_anomaly_identification     0-2
    structural_accuracy                  0-2
  Reference (reported separately, excluded from decision rule):
    short_vs_l1_reference               0-2
    long_vs_l2l3_reference              0-2

Each scored criterion includes a "quote" field: the verbatim phrase from the
generation that earned the score (required by rubric).
"""

import json
import os
import re
import time
from typing import Optional

HF_BASE_URL = "https://router.huggingface.co/v1"
DEFAULT_HF_JUDGE_MODEL = "Qwen/Qwen2.5-7B-Instruct"
CLAUDE_JUDGE_MODEL = "claude-sonnet-4-6"

SCORE_FIELDS_L2 = [
    "statistical_relational_completeness",
    "statistical_relational_precision",
]
SCORE_FIELDS_L3 = [
    "perceptual_cognitive_identification",
    "exception_anomaly_identification",
    "structural_accuracy",
]
SCORE_FIELDS_REF = [
    "short_vs_l1_reference",
    "long_vs_l2l3_reference",
]
ALL_SCORE_FIELDS = SCORE_FIELDS_L2 + SCORE_FIELDS_L3 + SCORE_FIELDS_REF


JUDGE_SYSTEM = """\
You are an expert evaluator of alt-text for data visualizations. \
You apply a structured rubric rigorously and provide evidence for every score \
by quoting the exact phrase from the generated text that earned it. \
If no phrase earns a score above 0, the quote field must be empty string."""


def _build_judge_prompt(example: dict, short: str, long: str) -> str:
    props = example["L1_properties"]
    chart_type, title, x_label, y_label, x_scale, y_scale = props
    gt_l1  = example.get("caption_L1", "")
    gt_l2l3 = example.get("caption_L2L3", "")
    scenegraph = example.get("scenegraph", "")
    datatable = example.get("datatable", "")

    generated = f"SHORT: {short}\nLONG: {long}"

    return f"""You are evaluating alt-text generated for a data visualization.

## Ground-truth chart information
Chart type: {chart_type}
Title: {title}
X-axis: {x_label} ({x_scale})
Y-axis: {y_label} ({y_scale})
Scenegraph: {scenegraph}
Datatable: {datatable}

## Reference captions (ground truth — for alignment scoring only)
Reference L1: {gt_l1}
Reference L2/L3: {gt_l2l3}

## Generated alt-text to evaluate
{generated}

## Scoring rubric

### L2 — Statistical & Relational Completeness (0-2)
2 = relevant statistical features present: extrema or start/end values, net change or rank ordering, AND at least one point-wise comparison
1 = some L2 features present but one key feature omitted
0 = no L2 content, or only one feature present with no comparison

### L2 — Statistical & Relational Precision (0-2)
2 = stated values accurate within reasonable tolerance; no misidentified extrema or rankings
1 = minor imprecision in one value; no directional or ranking errors
0 = one or more values substantially wrong, or extrema/rankings misidentified

### L3 — Perceptual & Cognitive Phenomena Identification (0-2)
2 = perceptual structure synthesized in natural-sounding language appropriate to chart type
1 = one perceptual feature noted, or pattern described in templatized phrasing
0 = no L3 content, or single undifferentiated claim requiring no visual perception

### L3 — Exception & Anomaly Identification (0-2)
2 = salient exception identified with approximate location and characterized as contrast to overall pattern in natural language
1 = exception noted but location imprecise, contrast absent, or language templatized
0 = absent when salient exception exists; or mentioned but wrong
Note: if no salient exception exists, award 2 unless the generation invents one.

### L3 — Structural Accuracy (0-2)
2 = shape or pattern accurately represented; no false uniformity; multi-series distinctions preserved
1 = one phase, category, or series missing or imprecise; no directional errors
0 = description gives a false mental model: wrong direction, collapsed multi-series, or pattern contradicts the chart

### Reference — Short vs. L1 VisText (0-2)
2 = generated SHORT is accurate to the reference L1 caption; may include more detail
1 = generated SHORT is missing details from the reference L1 caption
0 = generated SHORT is incorrect or substantially absent

### Reference — Long vs. L2/L3 VisText (0-2)
2 = generated LONG is an accurate interpretation reflective of the reference L2/L3 caption; may include more detail
1 = generated LONG is missing details present in the reference L2/L3 caption
0 = generated LONG interpretation greatly differs from the reference caption

## Instructions
For EACH criterion, quote the exact phrase from the generated text (SHORT or LONG) that earned the score.
If the score is 0 because content is absent, leave "quote" as empty string.
Do NOT reward content from the ground truth that is absent from the generation.

Return ONLY valid JSON in exactly this format (no markdown fences, no extra text):
{{
  "statistical_relational_completeness": {{"score": 0, "quote": ""}},
  "statistical_relational_precision":    {{"score": 0, "quote": ""}},
  "perceptual_cognitive_identification": {{"score": 0, "quote": ""}},
  "exception_anomaly_identification":    {{"score": 0, "quote": ""}},
  "structural_accuracy":                 {{"score": 0, "quote": ""}},
  "short_vs_l1_reference":              {{"score": 0, "quote": ""}},
  "long_vs_l2l3_reference":             {{"score": 0, "quote": ""}},
  "rationale": "one sentence summarizing the main strengths and weaknesses"
}}"""


def _parse_judge_response(raw: str) -> dict:
    """Parse judge JSON, tolerating markdown fences."""
    text = raw.strip()
    # Strip ```json ... ``` fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return _default_failed(raw)
        try:
            parsed = json.loads(m.group(0))
        except json.JSONDecodeError:
            return _default_failed(raw)

    return _clean_parsed(parsed, raw)


def _clean_parsed(parsed: dict, raw: str) -> dict:
    result = {}
    for field in ALL_SCORE_FIELDS:
        entry = parsed.get(field, {})
        if isinstance(entry, dict):
            raw_score = entry.get("score", 0)
            quote = str(entry.get("quote", ""))
        else:
            raw_score = entry
            quote = ""
        try:
            score = int(raw_score)
        except (TypeError, ValueError):
            score = 0
        if score not in (0, 1, 2):
            score = 0
        result[field] = {"score": score, "quote": quote}

    result["rationale"] = str(parsed.get("rationale", ""))
    result["parse_ok"] = True
    return result


def _default_failed(raw: str) -> dict:
    result = {f: {"score": 0, "quote": ""} for f in ALL_SCORE_FIELDS}
    result["rationale"] = f"PARSE_FAILED: {raw[:200]}"
    result["parse_ok"] = False
    return result


class ClaudeSonnetJudge:
    def __init__(self, max_retries: int = 3, retry_delay: float = 5.0):
        try:
            import anthropic
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "The Anthropic package is required for L2/L3 judging. "
                "Install project dependencies with `pip install -r requirements.txt`."
            ) from exc

        self.client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def judge(self, example: dict, short: str, long: str) -> dict:
        prompt = _build_judge_prompt(example, short, long)
        last_err = None

        for attempt in range(self.max_retries):
            try:
                msg = self.client.messages.create(
                    model=CLAUDE_JUDGE_MODEL,
                    max_tokens=1024,
                    system=JUDGE_SYSTEM,
                    messages=[{"role": "user", "content": prompt}],
                )
                raw = msg.content[0].text
                parsed = _parse_judge_response(raw)
                parsed["raw_judge_response"] = raw
                return parsed
            except Exception as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        failed = _default_failed(str(last_err))
        failed["raw_judge_response"] = str(last_err)
        return failed


class HFRouterJudge:
    def __init__(
        self,
        model_name: str = DEFAULT_HF_JUDGE_MODEL,
        max_retries: int = 3,
        retry_delay: float = 5.0,
    ):
        try:
            from openai import OpenAI
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "The OpenAI package is required for Hugging Face Router calls. "
                "Install project dependencies with `pip install -r requirements.txt`."
            ) from exc

        self.client = OpenAI(
            base_url=HF_BASE_URL,
            api_key=os.environ["HF_TOKEN"],
        )
        self.model_name = model_name
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def judge(self, example: dict, short: str, long: str) -> dict:
        prompt = _build_judge_prompt(example, short, long)
        last_err = None

        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": JUDGE_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=1024,
                    temperature=0.0,
                )
                raw = resp.choices[0].message.content or ""
                parsed = _parse_judge_response(raw)
                parsed["raw_judge_response"] = raw
                parsed["judge_model"] = self.model_name
                return parsed
            except Exception as e:
                last_err = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        failed = _default_failed(str(last_err))
        failed["raw_judge_response"] = str(last_err)
        failed["judge_model"] = self.model_name
        return failed


class LocalTransformersJudge:
    def __init__(
        self,
        model_name: str = DEFAULT_HF_JUDGE_MODEL,
        torch_dtype: str = "auto",
        device_map: str = "auto",
        cache_dir: str | None = None,
        max_new_tokens: int = 1024,
    ):
        from evals.local_transformers import LocalTransformersModel

        self.model_name = model_name
        self.max_new_tokens = max_new_tokens
        self.model = LocalTransformersModel(
            model_name=model_name,
            torch_dtype=torch_dtype,
            device_map=device_map,
            cache_dir=cache_dir,
        )

    def judge(self, example: dict, short: str, long: str) -> dict:
        prompt = _build_judge_prompt(example, short, long)
        raw = self.model.generate_chat(
            [
                {"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            max_new_tokens=self.max_new_tokens,
            temperature=0.0,
        )
        parsed = _parse_judge_response(raw)
        parsed["raw_judge_response"] = raw
        parsed["judge_model"] = self.model_name
        return parsed


def scores_from_result(result: dict) -> dict:
    """Extract just the integer scores (no quotes/rationale) for aggregation."""
    return {f: result[f]["score"] for f in ALL_SCORE_FIELDS}


def l2_score(result: dict) -> float:
    return sum(result[f]["score"] for f in SCORE_FIELDS_L2)


def l3_score(result: dict) -> float:
    return sum(result[f]["score"] for f in SCORE_FIELDS_L3)


def ref_score(result: dict) -> float:
    return sum(result[f]["score"] for f in SCORE_FIELDS_REF)
