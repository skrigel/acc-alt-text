"""
Small local inference wrapper for chat-style causal language models.

This module intentionally imports torch/transformers lazily so the rest of the
evaluation pipeline can still run in environments without local model support.
"""


def _resolve_torch_dtype(torch, dtype: str):
    if dtype == "auto":
        return "auto"
    if dtype in ("bf16", "bfloat16"):
        return torch.bfloat16
    if dtype in ("fp16", "float16"):
        return torch.float16
    if dtype in ("fp32", "float32"):
        return torch.float32
    raise ValueError(f"Unsupported torch dtype: {dtype}")


class LocalTransformersModel:
    def __init__(
        self,
        model_name: str,
        torch_dtype: str = "auto",
        device_map: str = "auto",
        cache_dir: str | None = None,
    ):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Local inference requires torch and transformers. "
                "Install them with `pip install -r requirements.txt`."
            ) from exc

        self.model_name = model_name
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=cache_dir)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=_resolve_torch_dtype(torch, torch_dtype),
            device_map=device_map,
            cache_dir=cache_dir,
        )
        self.model.eval()

    def generate_chat(
        self,
        messages: list[dict],
        max_new_tokens: int = 768,
        temperature: float = 0.0,
    ) -> str:
        if hasattr(self.tokenizer, "apply_chat_template"):
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        else:
            prompt = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in messages)
            prompt = f"{prompt}\n\nASSISTANT:"

        inputs = self.tokenizer(prompt, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}

        generation_kwargs = {
            **inputs,
            "max_new_tokens": max_new_tokens,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        if temperature > 0:
            generation_kwargs["do_sample"] = True
            generation_kwargs["temperature"] = temperature
        else:
            generation_kwargs["do_sample"] = False

        with self.torch.no_grad():
            outputs = self.model.generate(**generation_kwargs)

        generated_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
        return self.tokenizer.decode(generated_tokens, skip_special_tokens=True).strip()
