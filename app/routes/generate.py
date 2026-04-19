from fastapi import APIRouter
from core.llm_client import generate_alt_text
from models.schemas import GenerateRequest, GenerateResponse

router = APIRouter()

@router.get("/generate")
async def generate_text(req: GenerateRequest):
    # TODO parse all the things
    return generate_alt_text([],{})
