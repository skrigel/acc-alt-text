"""
LoRA/QLoRA fine-tuning for Qwen on VisText chart caption data.

Examples:
  python fine-tuning/train_qwen_lora.py \
    --model-name Qwen/Qwen2.5-1.5B-Instruct \
    --caption-mode short_long \
    --repr-key C \
    --output-dir results/qwen-vistext-lora

  python fine-tuning/train_qwen_lora.py \
    --model-name Qwen/Qwen2.5-3B-Instruct \
    --caption-mode l2l3_only \
    --use-4bit \
    --gradient-checkpointing
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evals.representations import build_l1_sentence, build_repr  # noqa: E402


DEFAULT_SYSTEM_PROMPT = (
    "You write accessible alt text for data visualizations. "
    "Be accurate, concise, and ground every claim in the provided chart data."
)

SHORT_LONG_INSTRUCTIONS = """\
Generate accessible alt text for this chart.

Return exactly:
SHORT: <one sentence covering chart type, title, axes, units, and ranges>
LONG: <one paragraph covering key values, extrema, comparisons, trends, visual shape, and anomalies>"""

L2L3_ONLY_INSTRUCTIONS = """\
The L1 structural description is already provided. Write only the LONG description.

The LONG description should cover:
- L2 statistical patterns: extrema, start/end values, net change or ranking, and at least one direct comparison.
- L3 perceptual insights: overall shape, trend, and any salient anomaly.

Return exactly:
LONG: <one paragraph covering L2 and L3>"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fine-tune Qwen with LoRA on VisText L1 and L2/L3 captions."
    )
    parser.add_argument(
        "--model-name",
        default="Qwen/Qwen2.5-7B-Instruct",
        help="Base Qwen chat model from Hugging Face or a local path.",
    )
    parser.add_argument(
        "--train-file",
        type=Path,
        default=REPO_ROOT / "data/vistext_train_test/data_validation.json",
        help="VisText JSON list with scenegraph, L1_properties, caption_L1, and caption_L2L3.",
    )
    parser.add_argument(
        "--eval-file",
        default=str(REPO_ROOT / "data/vistext_train_test/data_test.json"),
        help="Optional eval VisText JSON list. Pass an empty string to disable eval.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "results/qwen-vistext-lora",
        help="Where to save LoRA adapter checkpoints.",
    )
    parser.add_argument(
        "--caption-mode",
        choices=("short_long", "l2l3_only"),
        default="short_long",
        help="Train on combined L1+L2/L3 output or only L2/L3 with L1 supplied in the prompt.",
    )
    parser.add_argument(
        "--repr-key",
        choices=("A", "B", "C"),
        default="C",
        help="Chart representation from evals/representations.py.",
    )
    parser.add_argument("--max-train-samples", type=int, default=None)
    parser.add_argument("--max-eval-samples", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)

    parser.add_argument("--num-train-epochs", type=float, default=3.0)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--per-device-train-batch-size", type=int, default=1)
    parser.add_argument("--per-device-eval-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--max-seq-length", type=int, default=2048)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--save-steps", type=int, default=100)
    parser.add_argument("--eval-steps", type=int, default=100)

    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument(
        "--lora-target-modules",
        nargs="+",
        default=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        help="Qwen linear modules to adapt.",
    )

    parser.add_argument("--use-4bit", action="store_true", help="Use QLoRA 4-bit loading.")
    parser.add_argument(
        "--assistant-only-loss",
        action="store_true",
        help=(
            "Train loss only on assistant tokens. Requires a chat template with "
            "generation masks; leave off if TRL reports template support errors."
        ),
    )
    parser.add_argument(
        "--torch-dtype",
        choices=("auto", "bfloat16", "float16", "float32"),
        default="bfloat16",
    )
    parser.add_argument("--gradient-checkpointing", action="store_true")
    parser.add_argument("--resume-from-checkpoint", default=None)
    parser.add_argument("--push-to-hub", action="store_true")
    parser.add_argument("--hub-model-id", default=None)
    return parser.parse_args()


def load_vistext(path: Path, max_samples: int | None, seed: int) -> list[dict[str, Any]]:
    examples = json.loads(path.read_text())
    if not isinstance(examples, list):
        raise ValueError(f"{path} must contain a JSON list.")

    filtered = [
        ex
        for ex in examples
        if ex.get("caption_L1")
        and ex.get("caption_L2L3")
        and ex.get("scenegraph")
        and ex.get("L1_properties")
    ]
    rng = random.Random(seed)
    rng.shuffle(filtered)
    return filtered[:max_samples] if max_samples else filtered


def build_user_prompt(example: dict[str, Any], repr_key: str, caption_mode: str) -> str:
    repr_text = build_repr(example, repr_key)
    if caption_mode == "l2l3_only":
        return (
            f"{L2L3_ONLY_INSTRUCTIONS}\n\n"
            f"L1:\n{build_l1_sentence(example)}\n\n"
            f"Chart data:\n{repr_text}"
        )

    return f"{SHORT_LONG_INSTRUCTIONS}\n\nChart data:\n{repr_text}"


def build_assistant_response(example: dict[str, Any], caption_mode: str) -> str:
    l1 = str(example["caption_L1"]).strip()
    l2l3 = str(example["caption_L2L3"]).strip()
    if caption_mode == "l2l3_only":
        return f"LONG: {l2l3}"
    return f"SHORT: {l1}\nLONG: {l2l3}"


def to_chat_dataset(
    examples: list[dict[str, Any]],
    repr_key: str,
    caption_mode: str,
) -> Any:
    from datasets import Dataset

    rows = []
    for ex in examples:
        rows.append(
            {
                "img_id": str(ex.get("img_id", "")),
                "caption_id": str(ex.get("caption_id", "")),
                "messages": [
                    {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": build_user_prompt(ex, repr_key, caption_mode),
                    },
                    {
                        "role": "assistant",
                        "content": build_assistant_response(ex, caption_mode),
                    },
                ],
            }
        )
    return Dataset.from_list(rows)


def resolve_torch_dtype(torch_module: Any, dtype: str):
    if dtype == "auto":
        return "auto"
    return {
        "bfloat16": torch_module.bfloat16,
        "float16": torch_module.float16,
        "float32": torch_module.float32,
    }[dtype]


def main() -> None:
    args = parse_args()
    import torch
    from peft import LoraConfig, TaskType
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    torch.manual_seed(args.seed)

    tokenizer = AutoTokenizer.from_pretrained(args.model_name, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    quantization_config = None
    if args.use_4bit:
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name,
        torch_dtype=resolve_torch_dtype(torch, args.torch_dtype),
        device_map="auto",
        quantization_config=quantization_config,
        trust_remote_code=True,
    )
    model.config.use_cache = False

    train_examples = load_vistext(args.train_file, args.max_train_samples, args.seed)
    eval_examples = []
    if args.eval_file:
        eval_examples = load_vistext(Path(args.eval_file), args.max_eval_samples, args.seed + 1)

    train_dataset = to_chat_dataset(train_examples, args.repr_key, args.caption_mode)
    eval_dataset = (
        to_chat_dataset(eval_examples, args.repr_key, args.caption_mode)
        if eval_examples
        else None
    )

    peft_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=args.lora_target_modules,
        bias="none",
    )

    training_args = SFTConfig(
        output_dir=str(args.output_dir),
        num_train_epochs=args.num_train_epochs,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.per_device_train_batch_size,
        per_device_eval_batch_size=args.per_device_eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        max_length=args.max_seq_length,
        warmup_ratio=args.warmup_ratio,
        lr_scheduler_type="cosine",
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        eval_steps=args.eval_steps,
        eval_strategy="steps" if eval_dataset is not None else "no",
        save_strategy="steps",
        bf16=args.torch_dtype == "bfloat16",
        fp16=args.torch_dtype == "float16",
        gradient_checkpointing=args.gradient_checkpointing,
        optim="paged_adamw_8bit" if args.use_4bit else "adamw_torch",
        report_to="none",
        assistant_only_loss=args.assistant_only_loss,
        dataset_kwargs={"skip_prepare_dataset": False},
        push_to_hub=args.push_to_hub,
        hub_model_id=args.hub_model_id,
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        peft_config=peft_config,
    )

    print(f"Training examples: {len(train_dataset)}")
    print(f"Eval examples: {len(eval_dataset) if eval_dataset is not None else 0}")
    print(f"Output directory: {args.output_dir}")

    trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)
    trainer.save_model(str(args.output_dir))
    tokenizer.save_pretrained(str(args.output_dir))


if __name__ == "__main__":
    main()
