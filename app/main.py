from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routes.generate import router as generate_router


app = FastAPI(title="AltText Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate_router, prefix="/api")
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")

@app.get("/api/hello")
def greet_json():
    return {"Hello": "World!"}

