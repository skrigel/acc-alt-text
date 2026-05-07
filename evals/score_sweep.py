import json, os, time
from pathlib import Path
from evals.l1_eval import l1_full_eval
from evals.judge import ClaudeSonnetJudge

GEN_DIR = Path("results/generations")
SCORE_DIR = Path("results/scores")
SCORE_DIR.mkdir(parents=True, exist_ok=True)

def score_all():
    judge = ClaudeSonnetJudge()
    # Load validation data for ground truth
    all_examples = {e["img_id"]: e for e in json.loads(Path("data/vistext_train_test/data_validation.json").read_text())}

    for gen_file in GEN_DIR.glob("*.json"):
        score_file = SCORE_DIR / gen_file.name
        if score_file.exists(): continue
        
        print(f"Scoring {gen_file.name}...")
        generations = json.loads(gen_file.read_text())
        scores = []

        for gen in generations:
            ex = all_examples[gen["img_id"]]
            # 1. Programmatic L1
            l1_results = l1_full_eval(ex, gen["short"])
            # 2. Claude L2/L3 Judge
            judge_results = judge.judge(ex, gen["short"], gen["long"])
            
            scores.append({
                "img_id": gen["img_id"],
                "l1": l1_results,
                "judge": judge_results
            })
            # Respect Anthropic rate limits
            time.sleep(0.5)
            
        score_file.write_text(json.dumps(scores, indent=2))

if __name__ == "__main__":
    score_all()