"""
Generation harness for the 36-cell zero-shot sweep.
Updated: 
- Short: Strictly L1 (Elemental) content.
- Long: L1 + L2 + L3 (Structural + Statistical + Perceptual) content.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from evals.representations import build_repr
from evals.prompts import build_prompt, parse_output

# ── model configs ─────────────────────────────────────────────────────────────

HF_BASE_URL = "https://router.huggingface.co/v1"

MODELS = {
    "gpt-4o-mini": {
        "provider": "openai",
        "model_id": "gpt-4o-mini",
    },
    "llama": {
        "provider": "hf",
        "model_id": "meta-llama/Llama-3.1-8B-Instruct",
    },
    "mistral": {
        "provider": "hf",
        "model_id": "mistralai/Mistral-7B-Instruct-v0.3",
    },
    "qwen": {
        "provider": "hf",
        "model_id": "Qwen/Qwen2.5-7B-Instruct",
    },
}

REPR_KEYS   = ["A", "B", "C"]
PROMPT_KEYS = ["P1", "P2", "P3"]

GEN_DIR = Path("results/generations")
DATA_DIR = Path("data/vistext_train_test")
DEV_IDS_FILE = Path("data/eval/dev_ids.json")


# ── LLM clients ───────────────────────────────────────────────────────────────

def _make_openai_client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def _make_hf_client():
    from openai import OpenAI
    return OpenAI(
        base_url=HF_BASE_URL,
        api_key=os.environ["HF_TOKEN"],
    )


def _call_model(client, model_id: str, prompt: str, max_retries: int = 3) -> str:
    delay = 5.0
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=768, # Increased slightly to accommodate full L1-L3 analysis
                temperature=0.0,
            )
            content = resp.choices[0].message.content
            return content if content else ""
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"    retry {attempt+1}/{max_retries} after error: {e}", flush=True)
            time.sleep(delay * (attempt + 1))
    return ""


# ── data loading ──────────────────────────────────────────────────────────────

def _load_dev_examples(limit: int | None = None) -> list[dict]:
    dev_ids = set(json.loads(DEV_IDS_FILE.read_text()))
    all_examples = json.loads((DATA_DIR / "data_validation.json").read_text())
    dev = [e for e in all_examples if e["img_id"] in dev_ids]
    if limit:
        dev = dev[:limit]
    return dev


# ── single-cell run ───────────────────────────────────────────────────────────

def run_cell(
    model_key: str,
    repr_key: str,
    prompt_key: str,
    examples: list[dict],
    out_dir: Path,
    resume: bool = True,
) -> Path:
    cfg = MODELS[model_key]
    out_file = out_dir / f"{model_key}_{repr_key}_{prompt_key}.json"

    done: dict[int, dict] = {}
    if resume and out_file.exists():
        for item in json.loads(out_file.read_text()):
            done[item["img_id"]] = item

    remaining = [e for e in examples if e["img_id"] not in done]
    if not remaining:
        print(f"  [{model_key}|{repr_key}|{prompt_key}] already complete ({len(done)} examples)")
        return out_file

    client = _make_openai_client() if cfg["provider"] == "openai" else _make_hf_client()
    results = list(done.values())

    print(f"  [{model_key}|{repr_key}|{prompt_key}] {len(remaining)} to generate ...", flush=True)

    # Content constraints based on rubric
    constraints = (
        "Output Requirements:\n"
        "- SHORT: Strictly Level 1 content only (chart type, axes, title, ranges). No trends or comparisons.\n"
        "- LONG: Cumulative Level 1, 2, and 3 content (structure + statistical extrema/comparisons + perceptual trends/exceptions)."
    )

    for i, ex in enumerate(remaining):
        img_id = ex["img_id"]
        try:
            repr_text = build_repr(ex, repr_key)
            # Pass requirements to the prompt builder
            prompt = build_prompt(ex, repr_text, prompt_key, repr_key, custom_instructions=constraints)
            
            raw = _call_model(client, cfg["model_id"], prompt)
            short, long = parse_output(raw)
            
            results.append({
                "img_id": img_id,
                "chart_type": ex["L1_properties"][0],
                "short": short,
                "long": long,
                "raw_output": raw,
                "error": None,
            })
        except Exception as e:
            print(f"    ERROR img_id={img_id}: {e}", flush=True)
            results.append({
                "img_id": img_id,
                "chart_type": ex["L1_properties"][0],
                "short": "",
                "long": "",
                "raw_output": "",
                "error": str(e),
            })

        if (i + 1) % 10 == 0:
            out_file.write_text(json.dumps(results, indent=2))
            print(f"    checkpoint: {i+1}/{len(remaining)}", flush=True)

        if cfg["provider"] == "hf":
            time.sleep(1.0)

    out_file.write_text(json.dumps(results, indent=2))
    print(f"  [{model_key}|{repr_key}|{prompt_key}] done → {out_file}")
    return out_file


# ── ablation ──────────────────────────────────────────────────────────────────

def run_ablation(model_key, repr_key, prompt_key, examples, out_dir):
    """Passes chart title + L4 caption as 'page context' to the model."""
    out_file = out_dir / f"ablation_{model_key}_{repr_key}_{prompt_key}.json"
    client = _make_hf_client() if MODELS[model_key]["provider"] == "hf" else _make_openai_client()
    results = []

    constraints = (
        "Output Requirements:\n"
        "- SHORT: Strictly Level 1 structural content only.\n"
        "- LONG: Full L1 + L2 + L3 analysis. Use the provided 'Page Context' to ground L3 perceptual insights."
    )

    print(f"\n[Ablation] Running {model_key} with Page Context...")
    for ex in examples[:30]:
        img_id = ex["img_id"]
        # L4 context injection
        page_context = (
            f"Context from page: This chart titled '{ex['L1_properties'][1]}' "
            f"is discussed in the following snippet: {ex['caption_L2L3']}"
        )
        
        repr_text = build_repr(ex, repr_key)
        base_prompt = build_prompt(ex, repr_text, prompt_key, repr_key, custom_instructions=constraints)
        full_prompt = f"{page_context}\n\nTask Instructions:\n{base_prompt}"
        
        raw = _call_model(client, MODELS[model_key]["model_id"], full_prompt)
        short, long = parse_output(raw)
        results.append({
            "img_id": img_id, 
            "chart_type": ex["L1_properties"][0],
            "short": short, 
            "long": long, 
            "with_context": True,
            "raw_output": raw
        })
        
    out_file.write_text(json.dumps(results, indent=2))


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Run the 36-cell generation sweep.")
    parser.add_argument("--model",  choices=list(MODELS.keys()), default=None)
    parser.add_argument("--repr",   choices=REPR_KEYS,   default=None)
    parser.add_argument("--prompt", choices=PROMPT_KEYS, default=None)
    parser.add_argument("--limit",  type=int, default=None)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--ablate", action="store_true", help="Run the ablation study")
    args = parser.parse_args()

    GEN_DIR.mkdir(parents=True, exist_ok=True)
    examples = _load_dev_examples(limit=args.limit)

    if args.ablate:
        # Run ablation on specific subset if requested
        model = args.model or "gpt-4o-mini"
        run_ablation(model, args.repr or "A", args.prompt or "P1", examples, GEN_DIR)
        return

    models  = [args.model]  if args.model  else list(MODELS.keys())
    reprs   = [args.repr]   if args.repr   else REPR_KEYS
    prompts = [args.prompt] if args.prompt else PROMPT_KEYS

    total = len(models) * len(reprs) * len(prompts)
    done  = 0
    for model_key in models:
        for repr_key in reprs:
            for prompt_key in prompts:
                done += 1
                print(f"\n[{done}/{total}] {model_key} × {repr_key} × {prompt_key}")
                run_cell(
                    model_key, repr_key, prompt_key,
                    examples, GEN_DIR,
                    resume=not args.no_resume,
                )

    print("\nSweep complete.")

if __name__ == "__main__":
    main()