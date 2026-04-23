import asyncio
from dotenv import load_dotenv
from app.models.schemas import SvgData
import re
import os

load_dotenv()

import httpx
import os

HF_TOKEN = os.getenv("HF_TOKEN")
MODEL=os.getenv("MODEL_ID")

async def generate_alt_text(svgs: list[SvgData], context):
    # TODO: do we wna to pass in additional context?
    return await asyncio.gather(*[generate_single(i, svg) for i, svg in enumerate(svgs)])

async def call_llm(prompt: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api-inference.huggingface.co/v1/chat/completions",
            headers={"Authorization": f"Bearer {HF_TOKEN}"},
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024,
            },
            timeout=60.0
        )
        if response.status_code != 200 or not response.content:
            raise RuntimeError(
                f"HuggingFace API error {response.status_code}: {response.text!r}"
            )
        result = response.json()
    return result["choices"][0]["message"]["content"]


async def generate_single(i: int, svg: SvgData) -> dict:
    """
    Generates alt text for a single SVG visualization using its
    embedded context (ariaLabel, parentContext, etc.)
    """
    message = await call_llm(build_prompt(svg))
    return {
        "svg_index": i,
        "short_description": parse_section(message, "SHORT"),
        "long_description": parse_section(message, "LONG"),
    }

def build_prompt(svg: SvgData) -> str:
    # Use the structured context fields from SvgData directly
    context_lines = []
    if svg.parentContext:
        context_lines.append(svg.parentContext)   # already formatted by extract_svgs
    if svg.ariaLabel:
        context_lines.append(f"Aria label: {svg.ariaLabel}")
    if svg.ariaDescribedBy:
        context_lines.append(f"Aria described-by text: {svg.ariaDescribedBy}")

    context_block = "\n".join(context_lines) if context_lines else "No context available."

    svg_trimmed = re.sub(r'<defs>.*?</defs>', '', svg.html, flags=re.DOTALL)
    svg_trimmed = re.sub(r'<!--.*?-->', '', svg_trimmed, flags=re.DOTALL)
    svg_trimmed = svg_trimmed[:4000]

    return f"""You are an accessibility expert. Generate WCAG-compliant alt text for this SVG.

Page context:
{context_block}

SVG:
{svg_trimmed}

Respond in exactly this format:
SHORT: <one sentence for the alt attribute>
LONG: <detailed description covering axes, trends, and key data points for aria-describedby>
"""

def parse_section(text: str, section: str) -> str:
    """Extracts the SHORT or LONG section from the model response."""
    pattern = rf'{section}:\s*(.*?)(?=\n(?:SHORT|LONG):|$)'
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""