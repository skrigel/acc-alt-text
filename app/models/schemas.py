# TODO: define schemas for SVGs 

from pydantic import BaseModel, HttpUrl
from typing import List

class GenerateRequest(BaseModel):
    url: HttpUrl


class AltTextResult(BaseModel):
    svg: int
    short_desc: str
    long_desc: str

class GenerateResponse(BaseModel):
    results: List[AltTextResult]



