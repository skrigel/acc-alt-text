"""
Creates stratified dev (50) and held-out test (100) splits.

Dev  --> sampled from data_validation.json  (17 bar, 17 area, 16 line)
Test --> sampled from data_test.json        (34 bar, 33 area, 33 line)

Run once: python -m evals.build_dataset
Outputs: data/eval/dev_ids.json, data/eval/test_ids.json
"""
import json
import random
from collections import defaultdict
from pathlib import Path

VISTEXT_DIR = Path("data/vistext_train_test")
OUT_DIR = Path("data/eval")
SEED = 42

DEV_COUNTS  = {"bar": 17, "area": 17, "line": 16}
TEST_COUNTS = {"bar": 34, "area": 33, "line": 33}


def stratified_sample(data: list[dict], counts: dict[str, int], seed: int) -> list[str]:
    rng = random.Random(seed)
    groups: dict[str, list] = defaultdict(list)
    for ex in data:
        groups[ex["L1_properties"][0]].append(ex["img_id"])
    selected = []
    for chart_type, n in counts.items():
        pool = groups[chart_type]
        rng.shuffle(pool)
        selected.extend(pool[:n])
    return selected


def build():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    val_data  = json.loads((VISTEXT_DIR / "data_validation.json").read_text())
    test_data = json.loads((VISTEXT_DIR / "data_test.json").read_text())

    dev_ids  = stratified_sample(val_data,  DEV_COUNTS,  seed=SEED)
    test_ids = stratified_sample(test_data, TEST_COUNTS, seed=SEED + 1)

    (OUT_DIR / "dev_ids.json").write_text(json.dumps(dev_ids, indent=2))
    (OUT_DIR / "test_ids.json").write_text(json.dumps(test_ids, indent=2))

    print(f"Dev  set: {len(dev_ids)} examples  → {OUT_DIR}/dev_ids.json")
    print(f"Test set: {len(test_ids)} examples → {OUT_DIR}/test_ids.json")

    # Sanity-check: no overlap
    overlap = set(dev_ids) & set(test_ids)
    print(f"Overlap between dev and test: {len(overlap)} (should be 0)")


if __name__ == "__main__":
    build()
