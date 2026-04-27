from app.core.svg_extractor import parse_svg_to_chart
from fastapi import APIRouter
from app.core.llm_client import generate_alt_text
from app.models.schemas import GenerateRequest, GenerateResponse, SvgData
from bs4 import BeautifulSoup
from app.core.content_extractor import extract_visualizations
from app.core.svg_extractor import parse_svg_to_chart
from app.core.page_fetcher import fetch_rendered_html

from parser.schemas import ChartRepresentation

# from app.core.svg_extractor import 

router = APIRouter()

@router.post("/generate")
async def generate_text(req: GenerateRequest): 
    html = await fetch_rendered_html(req.url)
    svgs, imgs = extract_visualizations(html, base_url=req.url)

    vis_list = []
    for svg in svgs:
        chart: ChartRepresentation | None = parse_svg_to_chart(svg)
        # if (chart is not None and chart.!="unknown"):
        vis_list.append((svg, chart))

    return await generate_alt_text(vis_list)
                                   