import json
import pandas as pd
from pathlib import Path
import numpy as np

L2_FIELDS = [
    "statistical_relational_completeness",
    "statistical_relational_precision",
]
L3_FIELDS = [
    "perceptual_cognitive_identification",
    "exception_anomaly_identification",
    "structural_accuracy",
]


def _score(entry: dict, field: str) -> int:
    value = entry["judge"].get(field, {})
    if isinstance(value, dict):
        return int(value.get("score", 0))
    return int(value or 0)


def _config_from_path(score_file: Path) -> str:
    name = score_file.stem
    if name.startswith("ablation_"):
        name = name.removeprefix("ablation_")
    model, repr_key, prompt = name.rsplit("_", 2)
    return f"{model}-{repr_key}-{prompt}"


def aggregate():
    rows = []
    for score_file in Path("results/scores").glob("*.json"):
        data = json.loads(score_file.read_text())
        if not data:
            continue
        
        l1_scores = [d["l1"]["total_l1_score"] for d in data]
        l2_scores = [sum(_score(d, field) for field in L2_FIELDS) for d in data]
        l3_scores = [sum(_score(d, field) for field in L3_FIELDS) for d in data]
        halls = [1 if d["l1"]["example_has_hallucination"] else 0 for d in data]

        rows.append({
            "Config": _config_from_path(score_file),
            "L1": f"{np.mean(l1_scores):.2f} ± {np.std(l1_scores)/np.sqrt(len(l1_scores)):.2f}",
            "L2": f"{np.mean(l2_scores):.2f}",
            "L3": f"{np.mean(l3_scores):.2f}",
            "Total": f"{np.mean(l1_scores)+np.mean(l2_scores)+np.mean(l3_scores):.2f}",
            "Hallucination %": f"{np.mean(halls)*100:.1f}%",
            "L2_L3_Raw": np.mean(l2_scores) + np.mean(l3_scores),
            "Hallucination_Raw": np.mean(halls)
        })

    df = pd.DataFrame(rows)
    if df.empty:
        print("No score files found in results/scores.")
        return

    # Apply Decision Rule
    safe_df = df[df["Hallucination_Raw"] < 0.05]
    
    print(df.to_markdown())
    if safe_df.empty:
        print("\nSELECTED CONFIGURATION: No safe config found")
    else:
        winner = safe_df.loc[safe_df["L2_L3_Raw"].idxmax()]
        print(f"\nSELECTED CONFIGURATION: {winner['Config']}")

if __name__ == "__main__":
    aggregate()
