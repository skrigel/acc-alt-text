# Qwen LoRA Fine-Tuning

This folder contains a script for LoRA or QLoRA fine-tuning a Qwen chat model on
the VisText caption files in `data/vistext_train_test`.

The expected VisText examples contain:

- `scenegraph`
- `datatable`
- `L1_properties`
- `caption_L1`
- `caption_L2L3`

## Install

```bash
pip install -r fine-tuning/requirements.txt
```

## Train Combined L1 + L2/L3 Captions

This trains the model to produce both the short L1 description and the long
L2/L3 paragraph.

```bash
python fine-tuning/train_qwen_lora.py \
  --model-name Qwen/Qwen2.5-8B-Instruct \
  --caption-mode short_long \
  --repr-key C \
  --use-4bit \
  --gradient-checkpointing \
  --output-dir results/qwen-vistext-short-long-lora
```

Targets look like:

```text
SHORT: <caption_L1>
LONG: <caption_L2L3>
```

## Train L2/L3 Only

This supplies deterministic L1 facts in the prompt and trains only the long
description.

```bash
python fine-tuning/train_qwen_lora.py \
  --model-name Qwen/Qwen2.5-1.5B-Instruct \
  --caption-mode l2l3_only \
  --repr-key C \
  --use-4bit \
  --gradient-checkpointing \
  --output-dir results/qwen-vistext-l2l3-lora
```

Targets look like:

```text
LONG: <caption_L2L3>
```

## Useful Options

- `--train-file`: VisText JSON file used for training. Defaults to
  `data/vistext_train_test/data_validation.json` because this checkout does not
  include a separate `data_train.json`.
- `--eval-file`: VisText JSON file used for eval. Defaults to
  `data/vistext_train_test/data_test.json`; pass `--eval-file ""` to disable.
- `--repr-key`: chart representation from `evals/representations.py`.
  `C` is the default because it includes normalized chart data and L1 facts.
- `--max-train-samples` and `--max-eval-samples`: quick smoke-test limits.
- `--assistant-only-loss`: masks loss to assistant tokens when the Qwen chat
  template supports generation masks.

## Smoke Test

Use a tiny sample before launching a full run:

```bash
python fine-tuning/train_qwen_lora.py \
  --model-name Qwen/Qwen2.5-0.5B-Instruct \
  --caption-mode short_long \
  --max-train-samples 8 \
  --max-eval-samples 4 \
  --save-steps 2 \
  --eval-steps 2 \
  --output-dir results/qwen-vistext-smoke
```
