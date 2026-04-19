import asyncio
import anthropic

client = anthropic.Anthropic()

async def generate_alt_text(svgs: list[str],context: dict):
    results = []
    for i in range(len(svgs)):
        results.append(generate_single(i, svgs[i], context))
    return results

async def generate_single(i: int, svg: str, context: dict) -> dict:
    """
    Generates alt text for a SINGLE svg-based visualization, given as input an svg
    and a context dict extracted from an HTML page 
    """
 
    message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": build_prompt(svg, context)}]
        )
    result= { "svg_index": i, "short_description": "", "long_description": ""}
    return result

def build_prompt(svg: str, context: dict) -> str:
    return f"""You are an accessibility expert. Generate WCAG-compliant alt-text for this SVG chart.

Page context:
- Title: {context.get('title', '')}
- Headings: {', '.join(context.get('headings', []))}
- Captions: {', '.join(context.get('captions', []))}

SVG:
{svg[:3000]}  # TODO: find method that is not truncating

Return two parts:
1. SHORT: A one-sentence description (for the alt attribute)
2. LONG: A detailed description including axes, trends, and key findings (for aria-describedby)
"""