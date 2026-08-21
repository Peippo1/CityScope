import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.cities import router as cities_router
from .routes.investigations import router as investigations_router

app = FastAPI(title="CityScope API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("CITYSCOPE_WEB_ORIGIN", "http://localhost:3000")],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(cities_router)
app.include_router(investigations_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
