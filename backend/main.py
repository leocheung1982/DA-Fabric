"""
FastAPI application — optional REST API for DA-Fabric prototype.

Run from project root:

    uvicorn backend.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api_routes import router, service


@asynccontextmanager
async def lifespan(app: FastAPI):
    service.initialize()
    yield


app = FastAPI(
    title="DA-Fabric API",
    description="Demand-Aware Data Fabric Framework — Research Prototype API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "DA-Fabric"}
