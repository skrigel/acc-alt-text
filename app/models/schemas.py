# TODO: define schemas for SVGs 

from pydantic import BaseModel, HttpUrl
from typing import List

class GenerateRequest(BaseModel):
    url: str
    
class AltTextResult(BaseModel):
    svg_index: int
    raw: str
    short_description: str
    long_description: str
    
class ImgData(BaseModel):
    src: str
    existingAlt: str | None = None
    ariaLabel: str | None = None
    ariaDescribedBy: str | None = None
    parentContext: str | None = None

class GenerateResponse(BaseModel):
    results: List[AltTextResult]

class SvgData(BaseModel):
  html: str
  ariaLabel: str | None
  ariaDescribedBy: str | None
  parentContext: str | None


