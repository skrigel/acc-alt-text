# Evals

Evaluation pipeline for the accessible alt-text generation project. The pipeline covers dataset construction, generation sweeps, and multi-level scoring of model outputs against the [VisText](https://vis.csail.mit.edu/vistext/) benchmark.

## Overview

Alt-text quality is measured across three levels adapted from the VisText rubric:

| Level | Content | Scorer |
|-------|---------|--------|
| **L1** | Structural facts — chart type, title, axis labels, axis ranges | Programmatic (`l1_eval.py`) |
| **L2** | Statistical patterns — extrema, rank ordering, point-wise comparisons | Claude Sonnet judge (`judge.py`) |
| **L3** | Perceptual insights — overall shape, trends, anomalies | Claude Sonnet judge (`judge.py`) |

Each generated caption also receives a **hallucination score** (L1 tokens not sourced from ground-truth metadata) and **reference alignment scores** against the VisText human captions.

## Directory structure

```
evals/
├── build_dataset.py     # Build stratified dev/test splits
├── representations.py   # Chart input representations A, B, C
├── prompts.py           # Prompt templates P1, P2, P3 (and repr-C variants)
├── run_sweep.py         # Generation harness for the 36-cell sweep
├── l1_eval.py           # Programmatic L1 scorer
├── l2_l3_eval.py        # Local LLM L2/L3 judge (Qwen 2.5-7B)
├── judge.py             # Claude Sonnet L2/L3 judge (Anthropic API)
├── score_sweep.py       # Score all generations in results/generations/
├── aggregate_results.py # Aggregate scores and select best config
└── eval.ipynb           # Exploratory analysis notebook
```

## Setup

All commands are run from the **repo root**.

```bash
pip install -r requirements.txt
```

Required environment variables (place in a `.env` file at the repo root):

```
OPENAI_API_KEY=...   # for gpt-4o-mini generations
HF_TOKEN=...         # for HuggingFace-routed model generations (llama, mistral, qwen)
ANTHROPIC_API_KEY=.. # for the Claude Sonnet judge
```

## Step-by-step usage

### 1. Build dev/test splits

Creates stratified splits from the VisText validation and test sets. Run once.

```bash
python -m evals.build_dataset
```

Outputs:
- `data/eval/dev_ids.json` — 50 examples (17 bar, 17 area, 16 line) from `data_validation.json`
- `data/eval/test_ids.json` — 100 examples (34 bar, 33 area, 33 line) from `data_test.json`

### 2. Run the generation sweep

Sweeps all combinations of **4 models × 3 representations × 3 prompts** (36 cells) over the dev set.

```bash
python -m evals.run_sweep
```

Options:

| Flag | Description |
|------|-------------|
| `--model` | Run a single model: `gpt-4o-mini`, `llama`, `mistral`, `qwen` |
| `--repr` | Run a single representation: `A`, `B`, `C` |
| `--prompt` | Run a single prompt template: `P1`, `P2`, `P3` |
| `--limit N` | Cap the number of dev examples |
| `--no-resume` | Re-generate even if output file exists |
| `--ablate` | Run the page-context ablation study |

Outputs are saved to `results/generations/<model>_<repr>_<prompt>.json`.

**Representations:**

| Key | Description |
|-----|-------------|
| `A` | Raw VisText scenegraph text |
| `B` | Normalized JSON schema (chart type, axes, tick values, data points) |
| `C` | Repr B + deterministically pre-filled L1 sentence; model generates only L2/L3 |

**Prompt templates:**

| Key | Description |
|-----|-------------|
| `P1` | Minimal — bare instruction to generate alt-text |
| `P2` | WAI-ARIA grounded — role-playing with accessibility guidelines and a worked example |
| `P3` | Rubric grounded — explicit L1/L2/L3 breakdown with a worked example |

### 3. Score generations

Scores every file in `results/generations/` using the programmatic L1 scorer and the Claude Sonnet judge.

```bash
python -m evals.score_sweep
```

Outputs are saved to `results/scores/<model>_<repr>_<prompt>.json`.

### 4. Aggregate and select best config

Prints a markdown table of mean L1/L2/L3 scores per configuration and applies the decision rule: select the highest L2+L3 config with hallucination rate < 5%.

```bash
python -m evals.aggregate_results
```

## Scoring rubrics

### L1 (programmatic, max 10 points)

| Criterion | Max | Method |
|-----------|-----|--------|
| Chart type | 2 | Exact/synonym match (2), generic chart word (1) |
| Title | 2 | Fuzzy token match ≥ 90% (2), ≥ 50% (1) |
| Axis labels | 2 | Both correct (2), one correct (1) |
| Axis ranges | 2 | Both within 10% of ground truth (up to 2) |
| Hallucination | 2 | No extra tokens (2), one extra token (1), two or more (0) |

### L2/L3 (Claude Sonnet judge, max 10 points)

| Criterion | Level | Max |
|-----------|-------|-----|
| Statistical & relational completeness | L2 | 2 |
| Statistical & relational precision | L2 | 2 |
| Perceptual & cognitive phenomena identification | L3 | 2 |
| Exception & anomaly identification | L3 | 2 |
| Structural accuracy | L3 | 2 |

Reference alignment scores (`short_vs_l1_reference`, `long_vs_l2l3_reference`) are reported separately and excluded from the decision rule.

## Data

The VisText dataset files are expected at:

```
data/vistext_train_test/
├── data_train.json
├── data_validation.json
└── data_test.json
```

Each example contains `img_id`, `L1_properties` (chart type, title, x/y labels, x/y scales), `caption_L1`, `caption_L2L3`, `scenegraph`, and `datatable` fields.
