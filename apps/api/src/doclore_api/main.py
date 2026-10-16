from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from doclore_api.api.routes import router


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: Literal["doclore-api"]


app = FastAPI(
    title="DocLore API",
    description="Backend API for the DocLore developer documentation engine.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok", service="doclore-api")

