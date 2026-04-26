from app.core.svg_extractor import parse_svg_to_chart
from fastapi import APIRouter
from app.core.llm_client import generate_alt_text
from app.models.schemas import GenerateRequest, GenerateResponse, SvgData
from bs4 import BeautifulSoup
from app.core.content_extractor import extract_visualizations
from app.core.svg_extractor import parse_svg_to_chart
import requests

from parser.schemas import ChartRepresentation

# from app.core.svg_extractor import 

router = APIRouter()

@router.post("/generate")
async def generate_text(req: GenerateRequest):
    page_content = requests.get(req.url)
    svgs, imgs = extract_visualizations(page_content.text, base_url=req.url)

    vis_list = []
    for svg in svgs:
        chart: ChartRepresentation | None = parse_svg_to_chart(svg)
        if (chart is not None and chart.metadata.chartType!="unknown"):
            vis_list.append((svg, chart))

    return await generate_alt_text(vis_list)
                                   