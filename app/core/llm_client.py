import asyncio
from dotenv import load_dotenv
from app.models.schemas import SvgData
from app.core.svg_extractor import parse_svg_to_chart
from huggingface_hub import AsyncInferenceClient
import re
import os
import json
from openai import OpenAI

from parser.schemas import ChartRepresentation

load_dotenv()

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ["HF_TOKEN"],
)


MODEL ="katanemo/Arch-Router-1.5B:hf-inference"


async def generate_alt_text(svgs: list[tuple[SvgData,ChartRepresentation]]):
    # TODO: do we wna to pass in additional context?
    return await asyncio.gather(*[generate_single(i, svg, chart) for i, (svg, chart) in enumerate(svgs)])

async def call_llm(prompt: str) -> str:

    response =client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1024,
    )
    content = response.choices[0].message.content
    # TODO: better handling
    return content if content else 'N/A'


async def generate_single(i: int, svg: SvgData, chart: ChartRepresentation) -> dict:
    """
    Generates alt text for a single SVG visualization using its
    embedded context (ariaLabel, parentContext, etc.)
    """

    message = await call_llm(build_prompt(svg, chart))
    return {
        "svg_index": i,
        "short_description": parse_section(message, "SHORT"),
        "long_description": parse_section(message, "LONG"),
    }

def build_prompt(svg: SvgData, chart=None) -> str:
    # Use the structured context fields from SvgData directly
    context_lines = []
    if svg.parentContext:
        context_lines.append(svg.parentContext)
    if svg.ariaLabel:
        context_lines.append(f"Aria label: {svg.ariaLabel}")
    if svg.ariaDescribedBy:
        context_lines.append(f"Aria described-by text: {svg.ariaDescribedBy}")

    context_block = "\n".join(context_lines) if context_lines else "No context available."

    # If we have a parsed chart, use structured JSON; otherwise fall back to raw HTML
    if chart:
        chart_json = json.dumps(chart.model_dump(), indent=2)
        return f"""You are an accessibility expert. Generate WCAG-compliant alt text for this data visualization.

Page context:
{context_block}

Structured chart data:
{chart_json}

Using the structured data above, generate alt text that describes:
- Chart type and title
- Axes and their meanings
- Key trends, patterns, or insights from the data
- Important data points or ranges

Respond in exactly this format:
SHORT: <one sentence for the alt attribute>
LONG: <detailed description covering axes, trends, and key data points for aria-describedby>
"""
    else:
        # Fallback to raw SVG HTML
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