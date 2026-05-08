import re
from collections import defaultdict
import json
import argparse

VISTEXT_DATA_DIR = "data/vistext_train_test"

GRAPH_SYNONYMS = {
    "line": ["line chart", "line graph", "line plot", "line"],
    "bar": ["bar chart", "bar graph", "bar plot", "bar"],
    "scatter": ["scatter plot", "scatter chart", "scatter"],
    "pie": ["pie chart", "pie"],
    "area": ["area chart", "area graph", "area"],
    "histogram": ["histogram"],
}


GENERIC_CHART_WORDS = {"chart", "graph", "plot", "visualization", "figure"}

def build_img_index(split="train"):
    """
    converts vistext data (in vistext_train_test) into a dict mapping img_id to corresponding data (L1 properties, captions, and scenegraph/datatable)
    """
    with open(f"{VISTEXT_DATA_DIR}/data_{split}.json", "r") as f:
        data = json.load(f)

    img_index = defaultdict(list)

    for example in data:
        img_index[example["img_id"]] = example

    return dict(img_index)

def normalize(text):
    """
    normalizes text for comparison: lowercasing, removing punctuation (except for periods), and collapsing whitespace. Periods are kept to allow for decimal numbers in axis labels/ranges to be compared more easily.
    """
    text = str(text).lower()
    text = re.sub(r"[^\w\s.]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def fuzzy_contains(expected, output, threshold=0.9):
    """
    compares expected and output strings by checking if a certain percentage of the expected words are present in the output
    """
    # TODO rn just checks if exp words are in output, but might want to include some sort of penalty for extra words in output
    expected = normalize(expected)
    output = normalize(output)

    expected_words = expected.split()
    if not expected_words:
        return False

    matches = sum(1 for word in expected_words if word in output)
    return matches / len(expected_words) >= threshold

def extract_numbers(text):
    """
    gets all number in string (generated caption) to compare against expected axis ranges
    """
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", normalize(text))]


def score_chart_type(gt_l1_properties, gen_caption):
    gt_type_norm = normalize(gt_l1_properties["chart_type"])
    gen_caption_norm = normalize(gen_caption)

    synonyms = GRAPH_SYNONYMS.get(gt_type_norm, [gt_type_norm])

    # correct and specific chart type
    for synonym in synonyms:
        if normalize(synonym) in gen_caption_norm:
            return 2

    # TODO reevaluate; rn any generic chart word but idk about category?
    if any(word in gen_caption_norm.split() for word in GENERIC_CHART_WORDS):
        return 1

    return 0

def score_axis_labels(gt_l1_properties, gen_caption):
    # TODO threshold tweaking, pretty high for now because labels should ideally exacty match but might want to allow a little more flexibility? in case of odd str parsing or smth
    x_correct = fuzzy_contains(gt_l1_properties["x_label"], gen_caption, threshold=0.9)
    y_correct = fuzzy_contains(gt_l1_properties["y_label"], gen_caption, threshold=0.9)

    if x_correct and y_correct:
        return 2
    if x_correct or y_correct:
        return 1
    return 0

def axis_range_helper(gt_range, gen_caption):
    """
    compares generated caption axis range to expected axis range data
    checks if numbers in generated caption match expected numbers in ground truth
    then checks for "linear" or "categorical" if present in ground truth

    if "linear"/"categorical" is present in gt, penalizes by 0.5 points if not mentioned in generated caption
    otherwise maximum score of 1 determined solely by number matching
    """
    score = 0
    gt_numbers = extract_numbers(gt_range)
    gen_numbers = extract_numbers(gen_caption)

    if len(gt_numbers) != 2:
        print(f"Unexpected number of numbers in gt_range: {gt_range}")
        return 0

    for i, num in enumerate(gen_numbers[:-1]):
        left_tol = max(0.1 * abs(gt_numbers[0]), 1e-9)
        right_tol = max(0.1 * abs(gt_numbers[1]), 1e-9)
        if abs(num - gt_numbers[0]) <= left_tol:
            if abs(gen_numbers[i+1] - gt_numbers[1]) <= right_tol:
                score = 1
                break

    if gt_range.lower().split()[0] in ["linear", "categorical"]:
        score -= 0.5
        if gt_range.lower().split()[0] in gen_caption.lower():
            score += 0.5

    return max(score, 0)




def score_axis_ranges(gt_l1_properties, gen_caption):
    gt_x_range = gt_l1_properties["x_scale"]
    gt_y_range = gt_l1_properties["y_scale"]

    x_score = axis_range_helper(gt_x_range, gen_caption)
    y_score = axis_range_helper(gt_y_range, gen_caption)

    return x_score + y_score


def score_title(gt_l1_properties, gen_caption):
    # TODO threshold value tweaking
    gt_title = gt_l1_properties["title"]
    # accurately reproduced or faithfully paraphrased
    if fuzzy_contains(gt_title, gen_caption, threshold=0.9):
        return 2

    # present but wording deviates
    if fuzzy_contains(gt_title, gen_caption, threshold=0.5):
        return 1

    return 0

def _tokenize(text: str) -> list[str]:
    """
    Normalise and split text into tokens, stripping leading/trailing
    periods so sentence-final punctuation doesn't create phantom tokens.
    """
    return [t.strip(".") for t in normalize(text).split() if t.strip(".")]


def _source_l1_tokens(gt_l1_properties: dict) -> set[str]:
    """
    Build the full set of acceptable tokens for a correct L1 description.
    Includes chart-type synonyms, axis labels, scales, title words, and
    structural/stop-word vocabulary that any correct description may use.
    """
    stop = {
        "a", "an", "the", "of", "in", "on", "to", "for", "with", "from",
        "at", "by", "as", "is", "are", "and", "or", "its", "this", "that",
        "shows", "showing", "titled", "labeled", "label", "ranges", "range",
        "scale", "axis", "xaxis", "yaxis", "along", "while", "both", "per",
        "vs", "has", "have", "displays", "representing", "represents",
        "x", "y",
    }
    tokens: set[str] = set(stop) | GENERIC_CHART_WORDS

    gt_type_norm = normalize(gt_l1_properties["chart_type"])
    for syn in GRAPH_SYNONYMS.get(gt_type_norm, [gt_type_norm]):
        tokens.update(_tokenize(syn))

    for field in ("x_label", "y_label", "x_scale", "y_scale", "title"):
        tokens.update(_tokenize(gt_l1_properties[field]))

    return tokens


def score_hallucination(gt_l1_properties: dict, gen_caption: str) -> dict:
    """
    Detects tokens in the generated SHORT caption that are NOT in the source.

    Returns:
      hallucination_score        : 2 (none), 1 (one invented detail), 0 (multiple)
      hallucinated_tokens        : list[str] — tokens not in source
      example_has_hallucination  : bool (True if ≥1 hallucinated token)
      hallucination_token_rate   : hallucinated / total content tokens in output
    """
    source_tokens = _source_l1_tokens(gt_l1_properties)
    gen_tokens = _tokenize(gen_caption)

    # Exclude pure numbers — numeric drift is captured by axis-range scoring
    gen_content = [t for t in gen_tokens if not re.fullmatch(r"[\d.,]+", t)]

    hallucinated = [t for t in gen_content if t not in source_tokens]

    n_hall = len(hallucinated)
    if n_hall == 0:
        score = 2
    elif n_hall == 1:
        score = 1
    else:
        score = 0

    token_rate = n_hall / len(gen_content) if gen_content else 0.0

    return {
        "hallucination_score": score,
        "hallucinated_tokens": hallucinated,
        "example_has_hallucination": n_hall > 0,
        "hallucination_token_rate": token_rate,
    }


def normalize_l1_properties(example_or_props: dict) -> dict:
    """Return the L1 property dict expected by the individual scorers."""
    if "L1_properties" in example_or_props:
        props = example_or_props["L1_properties"]
        return {
            "chart_type": props[0],
            "title": props[1],
            "x_label": props[2],
            "y_label": props[3],
            "x_scale": props[4],
            "y_scale": props[5],
        }
    return example_or_props


def l1_full_eval(gt_l1_properties: dict, gen_caption: str) -> dict:
    gt_l1_properties = normalize_l1_properties(gt_l1_properties)
    chart_type_score = score_chart_type(gt_l1_properties, gen_caption)
    title_score = score_title(gt_l1_properties, gen_caption)
    axis_label_score = score_axis_labels(gt_l1_properties, gen_caption)
    axis_range_score = score_axis_ranges(gt_l1_properties, gen_caption)
    hall = score_hallucination(gt_l1_properties, gen_caption)
    total_l1_score = (
        chart_type_score
        + title_score
        + axis_label_score
        + axis_range_score
        + hall["hallucination_score"]
    )

    return {
        "chart_type_score": chart_type_score,
        "title_score": title_score,
        "axis_labels_score": axis_label_score,
        "axis_ranges_score": axis_range_score,
        "total_l1_score": total_l1_score,
        **hall,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--gen_caption_fp", type=str, required=True)
    parser.add_argument("--img_subset", nargs="+", type=str, default=[])
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    img_subset = args.img_subset
    gen_caption_file = args.gen_caption_fp
    debug = args.debug
    print(f"Running L1 eval for {img_subset=}")

    img_index = build_img_index("train")

    if not img_subset:
        img_subset = img_index.keys()

    # TODO reevaluate after deciding format of saving generated captions, right now assuming that generated captions for one experiment will be stored in one file in the format {"img": "caption", ...}
    with open(f"{gen_caption_file}", "r") as f:
        gen_caption_data = json.load(f)

    scores = {}

    for img in img_subset:
        gt_data = img_index[img]['L1_properties']
        gt_l1_properties = {
            "chart_type": gt_data[0],
            "title": gt_data[1],
            "x_label": gt_data[2],
            "y_label": gt_data[3],
            "x_scale": gt_data[4],
            "y_scale": gt_data[5],
        }
        gen_caption = gen_caption_data[img]
        if debug:
            print(f"{gen_caption=}")
            print(f"{gt_l1_properties=}")
        scores[img] = l1_full_eval(gt_l1_properties, gen_caption)

    print(scores)

    # TODO code for storing results after decide how we want to store
