import json
import pandas as pd
from pathlib import Path
import numpy as np

def aggregate():
    rows = []
    for score_file in Path("results/scores").glob("*.json"):
        # Parse filename: model_repr_prompt.json
        parts = score_file.stem.split("_")
        model, repr_key, prompt = parts[0], parts[1], parts[2]
        
        data = json.loads(score_file.read_text())
        
        l1_scores = [d["l1"]["total_l1_score"] for d in data]
        l2_scores = [d["judge"]["statistical_relational_completeness"]["score"] + 
                     d["judge"]["statistical_relational_precision"]["score"] for d in data]
        l3_scores = [d["judge"]["perceptual_cognitive_identification"]["score"] + 
                     d["judge"]["exception_anomaly_identification"]["score"] +
                     d["judge"]["structural_accuracy"]["score"] for d in data]
        halls = [1 if d["l1"]["hallucination_results"]["example_has_hallucination"] else 0 for d in data]

        rows.append({
            "Config": f"{model}-{repr_key}-{prompt}",
            "L1": f"{np.mean(l1_scores):.2f} ± {np.std(l1_scores)/np.sqrt(len(l1_scores)):.2f}",
            "L2": f"{np.mean(l2_scores):.2f}",
            "L3": f"{np.mean(l3_scores):.2f}",
            "Total": f"{np.mean(l1_scores)+np.mean(l2_scores)+np.mean(l3_scores):.2f}",
            "Hallucination %": f"{np.mean(halls)*100:.1f}%",
            "L2_L3_Raw": np.mean(l2_scores) + np.mean(l3_scores),
            "Hallucination_Raw": np.mean(halls)
        })

    df = pd.DataFrame(rows)
    # Apply Decision Rule
    safe_df = df[df["Hallucination_Raw"] < 0.05]
    winner = safe_df.loc[safe_df["L2_L3_Raw"].idxmax()] if not safe_df.empty else "No safe config found"
    
    print(df.to_markdown())
    print(f"\nSELECTED CONFIGURATION: {winner['Config']}")

if __name__ == "__main__":
    aggregate()