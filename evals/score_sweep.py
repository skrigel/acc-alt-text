import argparse
import json
import time
from pathlib import Path
from evals.l1_eval import l1_full_eval
from evals.judge import (
    ClaudeSonnetJudge,
    DEFAULT_HF_JUDGE_MODEL,
    HFRouterJudge,
    LocalTransformersJudge,
)

GEN_DIR = Path("results/generations")
SCORE_DIR = Path("results/scores")
SCORE_DIR.mkdir(parents=True, exist_ok=True)


def make_judge(
    kind: str,
    model_name: str | None = None,
    torch_dtype: str = "auto",
    device_map: str = "auto",
    cache_dir: str | None = None,
):
    if kind == "hf":
        return HFRouterJudge(model_name=model_name or DEFAULT_HF_JUDGE_MODEL)
    if kind == "local":
        return LocalTransformersJudge(
            model_name=model_name or DEFAULT_HF_JUDGE_MODEL,
            torch_dtype=torch_dtype,
            device_map=device_map,
            cache_dir=cache_dir,
        )
    if kind == "claude":
        return ClaudeSonnetJudge()
    raise ValueError(f"Unsupported judge: {kind}")


def score_all(
    judge_kind: str = "hf",
    judge_model: str | None = None,
    resume: bool = True,
    torch_dtype: str = "auto",
    device_map: str = "auto",
    cache_dir: str | None = None,
):
    # Load validation data for ground truth
    all_examples = {e["img_id"]: e for e in json.loads(Path("data/vistext_train_test/data_validation.json").read_text())}
    gen_files = sorted(GEN_DIR.glob("*.json"))
    if not gen_files:
        print(f"No generation files found in {GEN_DIR}.")
        return

    judge = make_judge(judge_kind, judge_model, torch_dtype, device_map, cache_dir)

    for gen_file in gen_files:
        score_file = SCORE_DIR / gen_file.name
        if resume and score_file.exists():
            continue
        
        print(f"Scoring {gen_file.name} with {judge_kind} judge...")
        generations = json.loads(gen_file.read_text())
        scores = []

        for gen in generations:
            ex = all_examples[gen["img_id"]]
            # 1. Programmatic L1
            l1_results = l1_full_eval(ex, gen["short"])
            # 2. LLM L2/L3 Judge
            judge_results = judge.judge(ex, gen["short"], gen["long"])
            
            scores.append({
                "img_id": gen["img_id"],
                "l1": l1_results,
                "judge": judge_results
            })
            time.sleep(0.5)
            
        score_file.write_text(json.dumps(scores, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Score generated captions.")
    parser.add_argument("--judge", choices=["hf", "local", "claude"], default="hf")
    parser.add_argument("--judge-model", default=None, help="Judge model id. Used with --judge hf or --judge local.")
    parser.add_argument("--torch-dtype", default="auto", choices=["auto", "bf16", "bfloat16", "fp16", "float16", "fp32", "float32"])
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--cache-dir", default=None, help="Optional local Hugging Face cache directory.")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()

    score_all(
        judge_kind=args.judge,
        judge_model=args.judge_model,
        resume=not args.no_resume,
        torch_dtype=args.torch_dtype,
        device_map=args.device_map,
        cache_dir=args.cache_dir,
    )


if __name__ == "__main__":
    main()
