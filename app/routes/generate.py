from fastapi import APIRouter
from app.core.llm_client import generate_alt_text
from app.models.schemas import GenerateRequest, GenerateResponse, SvgData
from bs4 import BeautifulSoup
from app.core.content_extractor import extract_visualizations

import requests

# from app.core.svg_extractor import 

router = APIRouter()

@router.post("/generate")
async def generate_text(req: GenerateRequest):
    page_content = requests.get(req.url)
    svgs, imgs = extract_visualizations(page_content.text, base_url=req.url)
    return await generate_alt_text(svgs, {})
                                   