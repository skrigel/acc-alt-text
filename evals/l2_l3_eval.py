import re
from collections import defaultdict
import json
import re
import argparse
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

VISTEXT_DATA_DIR = "data/vistext_train_test"

SCORE_FIELDS = [
    "statistical_relational_completeness",
    "statistical_relational_precision",
    "perceptual_cognitive_identification",
    "exception_anomaly_identification",
    "structural_accuracy",
    "reference_alignment"
]

def build_img_index(split="train"):
    """
    converts vistext data (in vistext_train_test) into a dict mapping img_id to corresponding data (L1 properties, captions, and scenegraph/datatable)
    """
    with open(f"../{VISTEXT_DATA_DIR}/data_{split}.json", "r") as f:
        data = json.load(f)

    img_index = defaultdict(list)

    for example in data:
        img_index[example["img_id"]] = example

    return dict(img_index)

def build_l2_l3_prompt(gt_data, gen_caption):
    datatable = gt_data.get("datatable", "")
    scenegraph = gt_data.get("scenegraph", "")
    gt_l2_l3 = gt_data.get("caption_L2L3", "")

    return f"""
You are evaluating chart alt text for accessibility.

You will receive:
1. The chart scenegraph
2. The chart datatable
3. A reference L1 caption
4. A reference L2/L3 caption
5. A generated caption to evaluate

Evaluate ONLY the generated caption. Do not reward unsupported claims.

Use this 0-2 rubric:

L2: Statistical & Relational Completeness
2 = relevant statistical features present, including extrema or start/end values, net change or rank ordering, and at least one point-wise comparison
1 = some L2 features present, but one key feature omitted
0 = no L2 content, or only one feature present with no comparison

L2: Statistical & Relational Precision
2 = stated values accurate within reasonable tolerance; no misidentified extrema or rankings
1 = minor imprecision in one value; no directional or ranking errors
0 = one or more values substantially wrong, or extrema/rankings misidentified

L3: Perceptual & Cognitive Phenomena Identification
2 = perceptual structure synthesized in natural-sounding language appropriate to chart type
1 = one perceptual feature noted, or pattern described in templated phrasing
0 = no L3 content, or single undifferentiated claim requiring no visual perception

L3: Exception & Anomaly Identification
2 = salient exception identified with approximate location and characterized as contrast to overall pattern
1 = exception noted but location imprecise, contrast absent, or language templated
0 = absent when salient exception exists, or mentioned but wrong
If no salient exception exists, give 2 unless the caption invents one.

L3: Structural Accuracy
2 = shape or pattern accurately represented; no false uniformity; multi-series distinctions preserved
1 = one phase, category, or series missing or imprecise; no directional errors
0 = false mental model: wrong direction, collapsed multi-series, or pattern contradicts chart

Reference Alignment Long vs. L2/L3 reference
2 = accurate interpretation reflective of L2/L3 reference caption; may include more details
1 = missing details to L2/L3 reference caption
0 = interpretation greatly differs from the L2/L3 reference caption

Return JSON only in this exact format:
{{
  "statistical_relational_completeness": 0,
  "statistical_relational_precision": 0,
  "perceptual_cognitive_identification": 0,
  "exception_anomaly_identification": 0,
  "structural_accuracy": 0,
  "reference_alignment": 0,
  "rationale": "brief explanation"
}}

Scenegraph:
{scenegraph}

Datatable:
{datatable}

Reference L2/L3 caption:
{gt_l2_l3}

Generated caption:
{gen_caption}
""".strip()


class L2L3Judge:
    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-7B-Instruct",
        torch_dtype=torch.bfloat16,
    ):
        self.model_name = model_name
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map="auto",
        )

    def generate_raw_response(self, prompt: str, max_new_tokens: int = 512) -> str:
        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                temperature=0.0,
            )

        response = self.tokenizer.decode(
            outputs[0][inputs["input_ids"].shape[-1]:],
            skip_special_tokens=True,
        )

        return response.strip()

    def judge(self, gt_data: str, gen_caption: str) -> dict:
        prompt = build_l2_l3_prompt(gt_data, gen_caption)
        raw_response = self.generate_raw_response(prompt)

        parsed = parse_judge_json(raw_response)

        return {
            "l2_l3_scores": {
                field: parsed.get(field, 0)
                for field in SCORE_FIELDS
            },
            "rationale": parsed.get("rationale", ""),
            "raw_judge_response": raw_response,
        }


def parse_judge_json(raw_response: str) -> dict:
    try:
        parsed = json.loads(raw_response)
        return clean_judge_scores(parsed)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", raw_response, re.DOTALL)

    if not match:
        return default_failed_parse(raw_response)

    try:
        parsed = json.loads(match.group(0))
        return clean_judge_scores(parsed)
    except:
        return default_failed_parse(raw_response)


def clean_judge_scores(parsed: dict) -> dict:
    cleaned = {}

    for field in SCORE_FIELDS:
        value = parsed.get(field, 0)

        try:
            value = int(value)
        except:
            print(f"error for {field}")
            value = 0
        if value not in [0, 1, 2]:
            print(f"unexpected value {value} for field {field}")
            value = 0
        cleaned[field] = value

    cleaned["rationale"] = str(parsed.get("rationale", ""))

    return cleaned


def default_failed_parse(raw_response: str) -> dict:
    print(f"failed to parse {raw_response[:300]}")
    return {
        "statistical_relational_completeness": 0,
        "statistical_relational_precision": 0,
        "perceptual_cognitive_identification": 0,
        "exception_anomaly_identification": 0,
        "structural_accuracy": 0,
        "rationale": f"Failed to parse judge response: {raw_response[:300]}",
    }


def evaluate_l2_l3(gt_data: dict, gen_caption: str, judge: L2L3Judge) -> dict:
    return judge.judge(gt_data, gen_caption)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--gen_caption_fp", type=str, required=True)
    parser.add_argument("--img_subset", nargs="+", type=str, default=[])

    args = parser.parse_args()
    img_subset = args.img_subset
    gen_caption_file = args.gen_caption_fp
    print(f"Running L2/L3 eval for {img_subset=}")

    img_index = build_img_index("train")

    if not img_subset:
        img_subset = img_index.keys()

    # TODO reevaluate after deciding format of saving generated captions, right now assuming that generated captions for one experiment will be stored in one file in the format {"img": "caption", ...}
    with open(f"{gen_caption_file}", "r") as f:
        gen_caption_data = json.load(f)

    scores = {}

    judge = L2L3Judge()

    for img in img_subset:
        gt_data = img_index[img]
        gen_caption = gen_caption_data[img]
        scores[img] = evaluate_l2_l3(gt_data, gen_caption, judge)

    # TODO code for storing results after decide how we want to store
