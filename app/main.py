from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AltText Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this before prod
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.include_router(alttext.router, prefix="/api")

@app.get("/")
def greet_json():
    return {"Hello": "World!"}

